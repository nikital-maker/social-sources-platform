import io
import json
import uuid

import pandas as pd

from backend.config import detect_platform_from_url
from backend.services.databricks_client import current_user, run_statement

_IMPORT_BATCH_SIZE = 500

_IMPORT_FIELD_KEYWORDS: dict[str, list[str]] = {
    "url":            ["url", "link", "account", "channel", "handle", "profile"],
    "team":           ["team"],
    "abuse_area":     ["abuse area", "abuse_area", "classification", "category", "abuse"],
    "sub_abuse_area": ["sub abuse", "sub_abuse", "subcategory", "sub category"],
    "notes":          ["note", "comment", "description", "remark"],
    "relevancy":      ["relevancy", "relevance", "relevant"],
}

_IMPORT_FIELD_LABELS: dict[str, str] = {
    "url":            "URL / Link column *",
    "team":           "Team column",
    "abuse_area":     "Abuse Area column",
    "sub_abuse_area": "Sub Abuse Area column",
    "notes":          "Notes column",
    "relevancy":      "Relevancy column",
}


def auto_map(columns: list[str]) -> dict[str, str | None]:
    mapping: dict[str, str | None] = {f: None for f in _IMPORT_FIELD_KEYWORDS}
    for field, keywords in _IMPORT_FIELD_KEYWORDS.items():
        for col in columns:
            if any(k in col.lower() for k in keywords):
                mapping[field] = col
                break
    return mapping


def parse_paste(text: str) -> pd.DataFrame | None:
    for sep in ("\t", ",", ";"):
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep)
            if len(df.columns) > 1:
                return df
        except Exception:
            pass
    return None


def safe_val(row: dict | pd.Series, col: str | None) -> str:
    if not col:
        return ""
    v = str(row.get(col, "") if isinstance(row, dict) else (row[col] if col in row.index else "")) or ""
    return "" if v.lower() in ("nan", "none") else v


def build_row_selects(
    raw_df: pd.DataFrame,
    mapping: dict[str, str | None],
    platform_override: str,
    col_hint_platform: str | None,
    meta_mapping: dict[str, str] | None = None,
    manual_values: dict[str, str] | None = None,
    user: str | None = None,
) -> tuple[list[str], int]:
    """Build SQL SELECT fragments for each valid row. Returns (row_selects, skipped_count)."""
    meta_mapping = meta_mapping or {}
    manual_values = manual_values or {}
    if user is None:
        user = current_user()
    user_esc = user.replace("'", "\\'")

    row_selects: list[str] = []
    skipped = 0

    for _, row in raw_df.iterrows():
        url_val = safe_val(row, mapping.get("url")).strip()
        if not url_val:
            skipped += 1
            continue

        if platform_override == "Auto-detect from URL":
            plat = detect_platform_from_url(url_val)
            if plat == "Unknown" and col_hint_platform:
                plat = col_hint_platform
        else:
            plat = platform_override

        def sv(field: str) -> str:
            v = safe_val(row, mapping.get(field))
            if not v:
                v = manual_values.get(field, "")
            return v.replace("'", "\\'")

        meta_dict = {k: safe_val(row, v) for k, v in meta_mapping.items() if safe_val(row, v)}
        meta_json = json.dumps(meta_dict).replace("'", "\\'")
        new_id = str(uuid.uuid4())
        url_esc = url_val.replace("'", "\\'")
        plat_esc = plat.replace("'", "\\'")

        row_selects.append(
            f"SELECT '{new_id}' AS id, '{url_esc}' AS url, '{plat_esc}' AS platform,"
            f" '{sv('team')}' AS team, '{sv('abuse_area')}' AS abuse_area,"
            f" '{sv('sub_abuse_area')}' AS sub_abuse_area, '{sv('notes')}' AS notes,"
            f" '{sv('relevancy')}' AS relevancy, '{meta_json}' AS metadata,"
            f" current_timestamp() AS added_at, '{user_esc}' AS added_by"
        )

    return row_selects, skipped


def execute_import(
    target_table: str,
    row_selects: list[str],
) -> dict:
    """Execute batched MERGE statements. Returns ImportResult dict."""
    if not row_selects:
        return {"imported": 0, "skipped": 0, "errors": [], "batches": 0}

    errors: list[str] = []
    total = len(row_selects)

    for batch_start in range(0, total, _IMPORT_BATCH_SIZE):
        batch = row_selects[batch_start: batch_start + _IMPORT_BATCH_SIZE]
        union_sql = "\nUNION ALL\n".join(batch)
        try:
            run_statement(f"""
                MERGE INTO {target_table} AS t
                USING ({union_sql}) AS src
                ON t.url = src.url
                WHEN MATCHED THEN UPDATE SET
                    platform = src.platform,
                    team = CASE WHEN src.team != '' THEN src.team ELSE t.team END,
                    abuse_area = CASE WHEN src.abuse_area != '' THEN src.abuse_area ELSE t.abuse_area END,
                    sub_abuse_area = CASE WHEN src.sub_abuse_area != '' THEN src.sub_abuse_area ELSE t.sub_abuse_area END,
                    notes = CASE WHEN src.notes != '' THEN src.notes ELSE t.notes END,
                    relevancy = CASE WHEN src.relevancy != '' THEN src.relevancy ELSE t.relevancy END,
                    metadata = CASE WHEN src.metadata != '{{}}' THEN src.metadata ELSE t.metadata END,
                    added_by = src.added_by
                WHEN NOT MATCHED THEN INSERT *
            """)
        except Exception as e:
            batch_num = batch_start // _IMPORT_BATCH_SIZE + 1
            errors.append(f"Batch {batch_num}: {e}")

    n_batches = (total + _IMPORT_BATCH_SIZE - 1) // _IMPORT_BATCH_SIZE
    return {
        "imported": total,
        "skipped": 0,
        "errors": errors,
        "batches": n_batches,
    }


def do_import(
    raw_df: pd.DataFrame,
    mapping: dict[str, str | None],
    platform_override: str,
    col_hint_platform: str | None,
    target_table: str,
    meta_mapping: dict[str, str] | None = None,
    manual_values: dict[str, str] | None = None,
    user: str | None = None,
) -> dict:
    row_selects, skipped = build_row_selects(
        raw_df, mapping, platform_override, col_hint_platform,
        meta_mapping, manual_values, user,
    )
    result = execute_import(target_table, row_selects)
    result["skipped"] = skipped
    return result
