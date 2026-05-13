import base64
import json
import os
import random
import re
import time

import pandas as pd

from backend.config import _GOOGLE_SA_DEFAULT_PATH, _GOOGLE_SA_CREDS_FOLDER
from backend.services.databricks_client import get_workspace_client


_GSHEETS_SCOPE = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _fix_sa_private_key(creds_dict: dict) -> dict:
    pk = creds_dict.get("private_key", "")
    if pk and "\n" not in pk and "-----BEGIN PRIVATE KEY-----" in pk:
        content = (
            pk.replace("-----BEGIN PRIVATE KEY-----", "")
            .replace("-----END PRIVATE KEY-----", "")
            .strip()
        )
        lines = [content[i: i + 64] for i in range(0, len(content), 64)]
        creds_dict["private_key"] = (
            "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"
        )
    return creds_dict


def _load_creds_dict_from_workspace(path: str) -> dict:
    resp = get_workspace_client().workspace.export(path=path)
    content = base64.b64decode(resp.content).decode("utf-8")
    return _fix_sa_private_key(json.loads(content))


def _authenticate(cred_path: str):
    from oauth2client.service_account import ServiceAccountCredentials
    import gspread

    if os.path.exists(cred_path):
        creds_dict = _fix_sa_private_key(json.loads(open(cred_path).read()))
    else:
        creds_dict = _load_creds_dict_from_workspace(cred_path)

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, _GSHEETS_SCOPE)
    return gspread.authorize(creds)


def _build_credentials_list() -> list[str]:
    """Return list of SA key paths: primary first, remaining files from folder shuffled."""
    primary = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", _GOOGLE_SA_DEFAULT_PATH)
    folder = _GOOGLE_SA_CREDS_FOLDER
    creds_list = [primary]

    primary_name = os.path.basename(primary)

    # Try local filesystem first (dev), fall back to Databricks workspace listing
    if os.path.isdir(folder):
        others = sorted(
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.endswith(".json") and f != primary_name
        )
    else:
        try:
            items = get_workspace_client().workspace.list(folder)
            others = sorted(
                item.path
                for item in (items or [])
                if item.path and item.path.endswith(".json") and os.path.basename(item.path) != primary_name
            )
        except Exception:
            others = []

    random.shuffle(others)
    creds_list.extend(others)
    return creds_list


def _execute_with_rotation(operation, operation_name: str = "operation", max_retries: int = 3):
    """Run operation(gspread_client) with credential rotation on quota/rate-limit errors."""
    from gspread.exceptions import APIError

    creds_list = _build_credentials_list()

    for cred_idx, cred_path in enumerate(creds_list):
        attempts = max_retries if cred_idx == 0 else 1
        name = os.path.basename(cred_path)

        for attempt in range(attempts):
            try:
                client = _authenticate(cred_path)
                return operation(client)

            except APIError as e:
                err = str(e).lower()
                is_rate_limit = any(x in err for x in ["429", "quota", "rate limit"])
                is_server_error = any(x in err for x in ["500", "502", "503"])

                if is_rate_limit:
                    print(f"[gsheets] Rate limit on {name}, rotating credential")
                    break

                if is_server_error and attempt < attempts - 1:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(wait)
                    continue

                if cred_idx < len(creds_list) - 1:
                    print(f"[gsheets] {name} failed ({e}), trying next credential")
                    break
                raise

            except Exception as e:
                if attempt < attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
                if cred_idx < len(creds_list) - 1:
                    print(f"[gsheets] {name} failed ({e}), trying next credential")
                    break
                raise

    raise Exception(f"[gsheets] All credentials exhausted during {operation_name}")


def parse_gsheet_url(url: str) -> tuple[str, int | None]:
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not m:
        raise ValueError("Not a valid Google Sheets URL.")
    spreadsheet_id = m.group(1)
    gid_m = re.search(r"gid=(\d+)", url)
    gid = int(gid_m.group(1)) if gid_m else None
    return spreadsheet_id, gid


def list_worksheets(spreadsheet_id: str) -> list[dict]:
    def _op(client):
        spreadsheet = client.open_by_key(spreadsheet_id)
        return [{"id": ws.id, "title": ws.title} for ws in spreadsheet.worksheets()]
    return _execute_with_rotation(_op, "list_worksheets")


def read_worksheet(spreadsheet_id: str, gid: int) -> dict:
    def _op(client):
        ws = client.open_by_key(spreadsheet_id).get_worksheet_by_id(gid)
        data = ws.get_all_values()
        if not data:
            return {"columns": [], "rows": []}
        return {"columns": data[0], "rows": data[1:]}
    return _execute_with_rotation(_op, "read_worksheet")


def read_worksheet_by_title(spreadsheet_id: str, tab_title: str) -> pd.DataFrame:
    def _op(client):
        ws = client.open_by_key(spreadsheet_id).worksheet(tab_title)
        data = ws.get_all_values()
        if not data:
            return pd.DataFrame()
        if len(data) == 1:
            return pd.DataFrame(columns=data[0])
        return pd.DataFrame(data[1:], columns=data[0])
    return _execute_with_rotation(_op, "read_worksheet_by_title")


def write_worksheet(spreadsheet_id: str, tab_title: str, rows: list[list]) -> int:
    def _op(client):
        ws = client.open_by_key(spreadsheet_id).worksheet(tab_title)
        ws.update(values=rows, range_name="A1")
        if ws.row_count > len(rows):
            ws.resize(rows=len(rows), cols=len(rows[0]) if rows else 1)
        return len(rows) - 1
    return _execute_with_rotation(_op, "write_worksheet")


def rename_worksheet(spreadsheet_id: str, old_title: str, new_title: str) -> None:
    def _op(client):
        ws = client.open_by_key(spreadsheet_id).worksheet(old_title)
        ws.update_title(new_title)
    _execute_with_rotation(_op, "rename_worksheet")
