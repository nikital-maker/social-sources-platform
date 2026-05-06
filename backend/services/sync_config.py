import json
import logging
import uuid

import pandas as pd

from backend.config import SYNC_CONFIG_TABLE, get_sources_table
from backend.services.databricks_client import run_query, run_statement
from backend.services.gsheets import read_worksheet_by_title
from backend.services.import_logic import build_row_selects, execute_import

log = logging.getLogger(__name__)


def list_sync_configs(team: str | None = None) -> list[dict]:
    where = f"WHERE team = '{team.replace(chr(39), chr(92)+chr(39))}'" if team else ""
    df = run_query(f"SELECT * FROM {SYNC_CONFIG_TABLE} {where} ORDER BY created_at DESC")
    if df.empty:
        return []
    df = df.fillna("")
    for col in ("sync_enabled",):
        if col in df.columns:
            df[col] = df[col].apply(lambda v: str(v).lower() in ("true", "1", "yes"))
    for col in ("gid", "sync_interval_minutes", "last_sync_rows"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df.to_dict(orient="records")


def get_sync_config(config_id: str) -> dict | None:
    esc = config_id.replace("'", "\\'")
    df = run_query(f"SELECT * FROM {SYNC_CONFIG_TABLE} WHERE id = '{esc}'")
    if df.empty:
        return None
    row = df.fillna("").iloc[0].to_dict()
    row["sync_enabled"] = str(row.get("sync_enabled", "")).lower() in ("true", "1", "yes")
    for col in ("gid", "sync_interval_minutes", "last_sync_rows"):
        val = pd.to_numeric(row.get(col, 0), errors="coerce")
        row[col] = 0 if pd.isna(val) else int(val)
    return row


def create_sync_config(
    spreadsheet_id: str,
    spreadsheet_url: str,
    spreadsheet_name: str,
    tab_title: str,
    gid: int,
    team: str,
    mapping_json: str = "{}",
    platform_override: str = "Auto-detect from URL",
    manual_values_json: str = "{}",
    meta_mapping_json: str = "{}",
    sync_interval_minutes: int = 30,
    user: str = "unknown",
) -> str:
    new_id = str(uuid.uuid4())

    def esc(v: str) -> str:
        return v.replace("'", "\\'")

    run_statement(f"""
        INSERT INTO {SYNC_CONFIG_TABLE}
        (id, spreadsheet_id, spreadsheet_url, spreadsheet_name, tab_title, gid, team,
         mapping_json, platform_override, manual_values_json, meta_mapping_json,
         sync_enabled, sync_interval_minutes, created_at, created_by)
        VALUES (
            '{new_id}', '{esc(spreadsheet_id)}', '{esc(spreadsheet_url)}',
            '{esc(spreadsheet_name)}', '{esc(tab_title)}', {gid}, '{esc(team)}',
            '{esc(mapping_json)}', '{esc(platform_override)}',
            '{esc(manual_values_json)}', '{esc(meta_mapping_json)}',
            true, {sync_interval_minutes}, current_timestamp(), '{esc(user)}'
        )
    """)
    return new_id


def update_sync_config(config_id: str, updates: dict) -> None:
    set_parts = []
    for key, val in updates.items():
        if val is None:
            continue
        if isinstance(val, bool):
            set_parts.append(f"{key} = {str(val).lower()}")
        elif isinstance(val, int):
            set_parts.append(f"{key} = {val}")
        else:
            set_parts.append(f"{key} = '{str(val).replace(chr(39), chr(92)+chr(39))}'")
    if not set_parts:
        return
    esc_id = config_id.replace("'", "\\'")
    run_statement(f"UPDATE {SYNC_CONFIG_TABLE} SET {', '.join(set_parts)} WHERE id = '{esc_id}'")


def delete_sync_config(config_id: str) -> None:
    esc_id = config_id.replace("'", "\\'")
    run_statement(f"DELETE FROM {SYNC_CONFIG_TABLE} WHERE id = '{esc_id}'")


def run_sync_for_config(config: dict) -> dict:
    """Pull new rows from a Google Sheet and import them. Returns ImportResult-like dict."""
    try:
        raw_df = read_worksheet_by_title(config["spreadsheet_id"], config["tab_title"])
        if raw_df.empty:
            _update_sync_status(config["id"], 0, None)
            return {"config_id": config["id"], "imported": 0, "skipped": 0, "errors": []}

        mapping = json.loads(config.get("mapping_json", "{}") or "{}")
        manual_values = json.loads(config.get("manual_values_json", "{}") or "{}")
        meta_mapping = json.loads(config.get("meta_mapping_json", "{}") or "{}")
        platform_override = config.get("platform_override", "Auto-detect from URL")
        target_table = get_sources_table(config["team"])

        row_selects, skipped = build_row_selects(
            raw_df=raw_df,
            mapping=mapping,
            platform_override=platform_override,
            col_hint_platform=None,
            meta_mapping=meta_mapping,
            manual_values=manual_values,
            user=config.get("created_by", "auto-sync"),
        )
        result = execute_import(target_table, row_selects)
        result["skipped"] = skipped
        _update_sync_status(config["id"], result["imported"], None)
        return {"config_id": config["id"], "imported": result["imported"], "skipped": skipped, "errors": result["errors"]}
    except Exception as e:
        log.exception("Sync failed for config %s", config["id"])
        _update_sync_status(config["id"], 0, str(e))
        return {"config_id": config["id"], "imported": 0, "skipped": 0, "errors": [str(e)]}


def _update_sync_status(config_id: str, rows: int, error: str | None) -> None:
    esc_id = config_id.replace("'", "\\'")
    if error:
        esc_err = error[:500].replace("'", "\\'")
        run_statement(
            f"UPDATE {SYNC_CONFIG_TABLE} SET last_sync_at = current_timestamp(), "
            f"last_sync_rows = {rows}, last_sync_error = '{esc_err}' WHERE id = '{esc_id}'"
        )
    else:
        run_statement(
            f"UPDATE {SYNC_CONFIG_TABLE} SET last_sync_at = current_timestamp(), "
            f"last_sync_rows = {rows}, last_sync_error = NULL WHERE id = '{esc_id}'"
        )
