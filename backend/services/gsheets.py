import base64
import json
import os
import re

import pandas as pd

from backend.config import _GOOGLE_SA_DEFAULT_PATH
from backend.services.databricks_client import get_workspace_client


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


def get_gsheets_client():
    from oauth2client.service_account import ServiceAccountCredentials
    import gspread

    scope = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    sa_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", _GOOGLE_SA_DEFAULT_PATH)

    if os.path.exists(sa_path):
        creds = ServiceAccountCredentials.from_json_keyfile_name(sa_path, scope)
        return gspread.authorize(creds)

    try:
        resp = get_workspace_client().workspace.export(path=sa_path)
        content = base64.b64decode(resp.content).decode("utf-8")
        creds_dict = json.loads(content)
        creds_dict = _fix_sa_private_key(creds_dict)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception as e:
        raise ValueError(f"Could not load Google service account from {sa_path}: {e}")


def parse_gsheet_url(url: str) -> tuple[str, int | None]:
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not m:
        raise ValueError("Not a valid Google Sheets URL.")
    spreadsheet_id = m.group(1)
    gid_m = re.search(r"gid=(\d+)", url)
    gid = int(gid_m.group(1)) if gid_m else None
    return spreadsheet_id, gid


def list_worksheets(spreadsheet_id: str) -> list[dict]:
    gc = get_gsheets_client()
    spreadsheet = gc.open_by_key(spreadsheet_id)
    return [{"id": ws.id, "title": ws.title} for ws in spreadsheet.worksheets()]


def read_worksheet(spreadsheet_id: str, gid: int) -> dict:
    gc = get_gsheets_client()
    ws = gc.open_by_key(spreadsheet_id).get_worksheet_by_id(gid)
    data = ws.get_all_values()
    if not data:
        return {"columns": [], "rows": []}
    return {"columns": data[0], "rows": data[1:]}


def read_worksheet_by_title(spreadsheet_id: str, tab_title: str) -> pd.DataFrame:
    gc = get_gsheets_client()
    ws = gc.open_by_key(spreadsheet_id).worksheet(tab_title)
    data = ws.get_all_values()
    if not data:
        return pd.DataFrame()
    if len(data) == 1:
        return pd.DataFrame(columns=data[0])
    return pd.DataFrame(data[1:], columns=data[0])


def write_worksheet(spreadsheet_id: str, tab_title: str, rows: list[list]) -> int:
    gc = get_gsheets_client()
    ws = gc.open_by_key(spreadsheet_id).worksheet(tab_title)
    ws.update(values=rows, range_name="A1")
    if ws.row_count > len(rows):
        ws.resize(rows=len(rows), cols=len(rows[0]) if rows else 1)
    return len(rows) - 1  # excluding header


def rename_worksheet(spreadsheet_id: str, old_title: str, new_title: str) -> None:
    gc = get_gsheets_client()
    ws = gc.open_by_key(spreadsheet_id).worksheet(old_title)
    ws.update_title(new_title)
