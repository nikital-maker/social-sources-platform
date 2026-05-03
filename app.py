import base64
import io
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from databricks.sdk import WorkspaceClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCES_TABLE = "af_delivery_dev.data_collection.social_sources"
STAGING_TABLE = "af_delivery_dev.data_collection.social_sources_staging"

PLATFORMS = ["Telegram", "Twitter/X", "TikTok", "Instagram", "YouTube", "Facebook", "Other"]
RELEVANCY_OPTIONS = ["Yes", "No", "Low", "Medium", "High", "True", "False"]

_PLATFORM_URL_PATTERNS = {
    "Telegram":  ["t.me/", "telegram.me/", "telegram.org"],
    "Twitter/X": ["twitter.com/", "x.com/"],
    "TikTok":    ["tiktok.com/"],
    "Instagram": ["instagram.com/", "instagr.am/"],
    "YouTube":   ["youtube.com/", "youtu.be/"],
    "Facebook":  ["facebook.com/", "fb.com/", "fb.watch/"],
}

_PLATFORM_COL_KEYWORDS = {
    "Telegram":  ["telegram"],
    "Twitter/X": ["twitter", "x.com", "tweet"],
    "TikTok":    ["tiktok", "tik tok"],
    "Instagram": ["instagram", "insta"],
    "YouTube":   ["youtube"],
    "Facebook":  ["facebook"],
}

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _check_statement_response(response) -> None:
    if response.status and response.status.error:
        raise Exception(response.status.error.message)


def run_query(query: str) -> pd.DataFrame:
    log.info(f"run_query: {query[:120].strip()}")
    try:
        wc = get_workspace_client()
        warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
        response = wc.statement_execution.execute_statement(
            statement=query,
            warehouse_id=warehouse_id,
            wait_timeout="50s",
        )
        _check_statement_response(response)
        if response.result is None or response.manifest is None:
            return pd.DataFrame()
        cols = [col.name for col in (response.manifest.schema.columns or [])]
        data = response.result.data_array or []
        log.info(f"run_query: returned {len(data)} rows")
        return pd.DataFrame(data, columns=cols)
    except Exception as e:
        log.error(f"run_query failed: {e}")
        raise


def run_statement(statement: str) -> None:
    log.info(f"run_statement: {statement[:120].strip()}")
    try:
        wc = get_workspace_client()
        warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
        response = wc.statement_execution.execute_statement(
            statement=statement,
            warehouse_id=warehouse_id,
            wait_timeout="50s",
        )
        _check_statement_response(response)
        log.info("run_statement: OK")
    except Exception as e:
        log.error(f"run_statement failed: {e}")
        raise


@st.cache_resource
def get_workspace_client():
    return WorkspaceClient()


def current_user() -> str:
    try:
        return get_workspace_client().current_user.me().user_name or "unknown"
    except Exception:
        return "local_dev"


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

def detect_platform_from_url(url: str) -> str:
    if not url:
        return "Unknown"
    url_lower = url.lower()
    for platform, patterns in _PLATFORM_URL_PATTERNS.items():
        if any(p in url_lower for p in patterns):
            return platform
    return "Unknown"


def detect_platform_from_column_name(col: str) -> str | None:
    col_lower = col.lower()
    for platform, keywords in _PLATFORM_COL_KEYWORDS.items():
        if any(k in col_lower for k in keywords):
            return platform
    return None


# ---------------------------------------------------------------------------
# Google Sheets helpers (mirrors Utils_v2 auth logic)
# ---------------------------------------------------------------------------

def _fix_sa_private_key(creds_dict: dict) -> dict:
    pk = creds_dict.get("private_key", "")
    if pk and "\n" not in pk and "-----BEGIN PRIVATE KEY-----" in pk:
        content = (
            pk.replace("-----BEGIN PRIVATE KEY-----", "")
            .replace("-----END PRIVATE KEY-----", "")
            .strip()
        )
        lines = [content[i : i + 64] for i in range(0, len(content), 64)]
        creds_dict["private_key"] = (
            "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"
        )
    return creds_dict


_GOOGLE_SA_DEFAULT_PATH = (
    "/Workspace/Users/nikital@activefence.com/Upload to gsheet files/best-gsaccount-5b4811cedbed.json"
)


def _get_gsheets_client():
    from oauth2client.service_account import ServiceAccountCredentials
    import gspread

    scope = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]

    sa_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", _GOOGLE_SA_DEFAULT_PATH)

    # Option 1: direct file access (works on clusters / local)
    if os.path.exists(sa_path):
        creds = ServiceAccountCredentials.from_json_keyfile_name(sa_path, scope)
        return gspread.authorize(creds)

    # Option 2: read via WorkspaceClient (works in Databricks Apps where /Workspace isn't mounted)
    try:
        resp = get_workspace_client().workspace.export(path=sa_path)
        content = base64.b64decode(resp.content).decode("utf-8")
        creds_dict = json.loads(content)
        creds_dict = _fix_sa_private_key(creds_dict)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception as e:
        raise ValueError(f"Could not load Google service account from {sa_path}: {e}")


def _parse_gsheet_url(url: str) -> tuple:
    """Return (spreadsheet_id, gid_or_None) from a Google Sheets URL."""
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not m:
        raise ValueError("Not a valid Google Sheets URL.")
    spreadsheet_id = m.group(1)
    gid_m = re.search(r"gid=(\d+)", url)
    gid = int(gid_m.group(1)) if gid_m else None
    return spreadsheet_id, gid


# ---------------------------------------------------------------------------
# Cached data loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_sources() -> pd.DataFrame:
    return run_query(f"SELECT * FROM {SOURCES_TABLE} ORDER BY added_at DESC")


@st.cache_data(ttl=60)
def load_staging() -> pd.DataFrame:
    return run_query(
        f"""
        SELECT s.*
        FROM {STAGING_TABLE} s
        LEFT ANTI JOIN {SOURCES_TABLE} m ON s.url = m.url
        """
    )


# ---------------------------------------------------------------------------
# Multi-value filter helpers (comma-separated column values)
# ---------------------------------------------------------------------------

def get_multivalue_options(df: pd.DataFrame, column: str) -> list:
    values = set()
    for val in df[column].dropna():
        for v in str(val).split(","):
            v = v.strip()
            if v:
                values.add(v)
    return sorted(values)


def multivalue_mask(series: pd.Series, selected: list) -> pd.Series:
    selected_set = set(selected)
    def matches(val):
        if pd.isna(val) or not str(val).strip():
            return False
        return bool({v.strip() for v in str(val).split(",")} & selected_set)
    return series.apply(matches)


# ---------------------------------------------------------------------------
# Page: Sources Browser
# ---------------------------------------------------------------------------

def _delete_sources_by_ids(ids: list[str]) -> None:
    escaped = ", ".join(f"'{i.replace(chr(39), chr(39)*2)}'" for i in ids)
    run_statement(f"DELETE FROM {SOURCES_TABLE} WHERE id IN ({escaped})")


@st.dialog("Confirm deletion")
def _confirm_delete_dialog():
    ids = st.session_state.get("_pending_delete_ids", [])
    st.warning(f"You are about to permanently delete **{len(ids)} source(s)**. This cannot be undone.")
    col_ok, col_cancel = st.columns(2)
    if col_ok.button("Yes, delete", type="primary", use_container_width=True):
        _delete_sources_by_ids(ids)
        del st.session_state["_pending_delete_ids"]
        st.session_state["_delete_done"] = True
        st.rerun()
    if col_cancel.button("Cancel", use_container_width=True):
        del st.session_state["_pending_delete_ids"]
        st.rerun()


def page_sources_browser():
    st.title("Sources Browser")

    try:
        df = load_sources()
    except Exception as e:
        st.error(f"Failed to load sources: {e}")
        st.code(f"host={os.environ.get('DATABRICKS_HOST','(not set)')}\nwarehouse={os.environ.get('DATABRICKS_WAREHOUSE_ID','(not set)')}\ntoken_set={'DATABRICKS_TOKEN' in os.environ}")
        return

    if df.empty:
        st.info("No sources yet. Use Import or the sidebar form to add sources.")
        return

    col_export, col_count = st.columns([1, 5])
    col_export.download_button(
        "Export CSV",
        data=df.to_csv(index=False).encode(),
        file_name="social_sources.csv",
        mime="text/csv",
    )

    st.divider()

    with st.expander("Filters", expanded=True):
        r1c1, r1c2, r1c3 = st.columns(3)
        r2c1, r2c2, r2c3 = st.columns(3)

        platform_opts = ["All"] + sorted(df["platform"].dropna().unique().tolist())
        sel_platform = r1c1.selectbox("Platform", platform_opts)
        sel_team = r1c2.multiselect("Team", get_multivalue_options(df, "team"))
        sel_abuse = r1c3.multiselect("Abuse Area", get_multivalue_options(df, "abuse_area"))
        sel_sub = r2c1.multiselect("Sub Abuse Area", get_multivalue_options(df, "sub_abuse_area"))
        sel_relevancy = r2c2.multiselect("Relevancy", get_multivalue_options(df, "relevancy"))
        keyword = r2c3.text_input("Keyword (URL / Notes)")

    filtered = df.copy()
    if sel_platform != "All":
        filtered = filtered[filtered["platform"] == sel_platform]
    if sel_team:
        filtered = filtered[multivalue_mask(filtered["team"], sel_team)]
    if sel_abuse:
        filtered = filtered[multivalue_mask(filtered["abuse_area"], sel_abuse)]
    if sel_sub:
        filtered = filtered[multivalue_mask(filtered["sub_abuse_area"], sel_sub)]
    if sel_relevancy:
        filtered = filtered[multivalue_mask(filtered["relevancy"], sel_relevancy)]
    if keyword:
        mask = (
            filtered["url"].str.contains(keyword, case=False, na=False)
            | filtered["notes"].str.contains(keyword, case=False, na=False)
        )
        filtered = filtered[mask]

    col_count.caption(f"{len(filtered)} of {len(df)} sources")

    display = filtered.copy()
    display.insert(0, "Select", False)
    edited = st.data_editor(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={"Select": st.column_config.CheckboxColumn(required=True)},
        disabled=[c for c in display.columns if c != "Select"],
    )

    selected_ids = edited.loc[edited["Select"] == True, "id"].tolist()
    if selected_ids:
        selected_rows = filtered[filtered["id"].isin(selected_ids)]
        btn_del, btn_csv = st.columns([1, 1])
        with btn_del:
            if st.button(f"Delete {len(selected_ids)} selected row(s)", type="primary", use_container_width=True):
                st.session_state["_pending_delete_ids"] = selected_ids
                _confirm_delete_dialog()
        with btn_csv:
            st.download_button(
                f"Download {len(selected_ids)} selected as CSV",
                data=selected_rows.to_csv(index=False).encode(),
                file_name="selected_sources.csv",
                mime="text/csv",
                use_container_width=True,
            )

    if st.session_state.get("_delete_done"):
        del st.session_state["_delete_done"]
        load_sources.clear()
        st.rerun()


# ---------------------------------------------------------------------------
# Page: Import Sources
# ---------------------------------------------------------------------------

_IMPORT_FIELD_KEYWORDS = {
    "url":           ["url", "link", "account", "channel", "handle", "profile"],
    "team":          ["team"],
    "abuse_area":    ["abuse area", "abuse_area", "classification", "category", "abuse"],
    "sub_abuse_area":["sub abuse", "sub_abuse", "subcategory", "sub category"],
    "notes":         ["note", "comment", "description", "remark"],
    "relevancy":     ["relevancy", "relevance", "relevant"],
}

_IMPORT_FIELD_LABELS = {
    "url":           "URL / Link column *",
    "team":          "Team column",
    "abuse_area":    "Abuse Area column",
    "sub_abuse_area":"Sub Abuse Area column",
    "notes":         "Notes column",
    "relevancy":     "Relevancy column",
}


def _auto_map(columns: list) -> dict:
    mapping = {f: None for f in _IMPORT_FIELD_KEYWORDS}
    for field, keywords in _IMPORT_FIELD_KEYWORDS.items():
        for col in columns:
            if any(k in col.lower() for k in keywords):
                mapping[field] = col
                break
    return mapping


def _parse_paste(text: str) -> pd.DataFrame | None:
    for sep in ("\t", ",", ";"):
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep)
            if len(df.columns) > 1:
                return df
        except Exception:
            pass
    return None


def _safe_val(row, col):
    if not col:
        return ""
    v = str(row.get(col, "") or "")
    return "" if v.lower() in ("nan", "none") else v


def _render_import_ui(raw_df: pd.DataFrame):
    st.subheader("Column Mapping")
    cols_with_none = [None] + list(raw_df.columns)
    auto = _auto_map(list(raw_df.columns))

    def default_idx(field):
        val = auto.get(field)
        return cols_with_none.index(val) if val and val in cols_with_none else 0

    left, right = st.columns(2)
    mapping = {}
    with left:
        for field in ["url", "team", "abuse_area"]:
            mapping[field] = st.selectbox(
                _IMPORT_FIELD_LABELS[field], cols_with_none, index=default_idx(field)
            )
    with right:
        for field in ["sub_abuse_area", "notes", "relevancy"]:
            mapping[field] = st.selectbox(
                _IMPORT_FIELD_LABELS[field], cols_with_none, index=default_idx(field)
            )

    if not mapping["url"]:
        st.warning("Select the URL column to continue.")
        return

    col_hint_platform = detect_platform_from_column_name(mapping["url"])
    platform_options = ["Auto-detect from URL"] + PLATFORMS
    default_plat_idx = platform_options.index(col_hint_platform) if col_hint_platform and col_hint_platform in platform_options else 0

    platform_override = st.selectbox(
        "Platform override",
        platform_options,
        index=default_plat_idx,
        help="Auto-detect reads platform from each URL. Or force a single platform for all rows.",
    )
    if col_hint_platform and platform_override == "Auto-detect from URL":
        st.caption(f"Column name suggests platform: **{col_hint_platform}**")

    # Metadata field mapping
    st.subheader("Metadata Fields")
    st.caption("Map additional source columns to metadata fields stored as JSON on each source.")
    already_mapped = {v for v in mapping.values() if v}
    remaining_cols = [c for c in raw_df.columns if c not in already_mapped]
    if remaining_cols:
        meta_init = pd.DataFrame({
            "Include": [False] * len(remaining_cols),
            "Source Column": remaining_cols,
            "Metadata Field Name": remaining_cols,
        })
        meta_edited = st.data_editor(
            meta_init,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Include": st.column_config.CheckboxColumn(required=True),
                "Source Column": st.column_config.TextColumn(disabled=True),
                "Metadata Field Name": st.column_config.TextColumn(),
            },
        )
        meta_mapping = {
            row["Metadata Field Name"].strip(): row["Source Column"]
            for _, row in meta_edited[meta_edited["Include"] == True].iterrows()
            if row["Metadata Field Name"].strip()
        }
    else:
        st.caption("All columns are already mapped to standard fields.")
        meta_mapping = {}

    # Preview
    preview = []
    for _, row in raw_df.head(5).iterrows():
        url_val = _safe_val(row, mapping["url"])
        if platform_override == "Auto-detect from URL":
            plat = detect_platform_from_url(url_val) if url_val else ""
            if plat == "Unknown" and col_hint_platform:
                plat = col_hint_platform
        else:
            plat = platform_override
        meta_dict = {k: _safe_val(row, v) for k, v in meta_mapping.items() if _safe_val(row, v)}
        preview.append({
            "url": url_val,
            "platform": plat,
            "team": _safe_val(row, mapping["team"]),
            "abuse_area": _safe_val(row, mapping["abuse_area"]),
            "sub_abuse_area": _safe_val(row, mapping["sub_abuse_area"]),
            "notes": _safe_val(row, mapping["notes"]),
            "relevancy": _safe_val(row, mapping["relevancy"]),
            "metadata": json.dumps(meta_dict) if meta_dict else "{}",
        })

    st.subheader(f"Preview — first {len(preview)} of {len(raw_df)} rows")
    st.dataframe(pd.DataFrame(preview), use_container_width=True)

    if st.button(f"Import {len(raw_df)} rows", type="primary"):
        _do_import(raw_df, mapping, platform_override, col_hint_platform, meta_mapping)


def _do_import(raw_df, mapping, platform_override, col_hint_platform, meta_mapping=None):
    meta_mapping = meta_mapping or {}
    user = current_user().replace("'", "\\'")
    inserted = skipped = 0
    errors = []
    progress = st.progress(0, text="Importing…")
    total = len(raw_df)

    for i, (_, row) in enumerate(raw_df.iterrows()):
        url_val = _safe_val(row, mapping["url"]).strip()
        if not url_val:
            skipped += 1
            progress.progress((i + 1) / total)
            continue

        if platform_override == "Auto-detect from URL":
            plat = detect_platform_from_url(url_val)
            if plat == "Unknown" and col_hint_platform:
                plat = col_hint_platform
        else:
            plat = platform_override

        def s(field):
            return _safe_val(row, mapping.get(field)).replace("'", "\\'")

        meta_dict = {k: _safe_val(row, v) for k, v in meta_mapping.items() if _safe_val(row, v)}
        metadata_json = json.dumps(meta_dict).replace("'", "\\'")

        new_id = str(uuid.uuid4())
        url_esc = url_val.replace("'", "\\'")
        plat_esc = plat.replace("'", "\\'")
        try:
            run_statement(f"""
                MERGE INTO {SOURCES_TABLE} AS t
                USING (SELECT
                    '{new_id}'                    AS id,
                    '{url_esc}'                   AS url,
                    '{plat_esc}'                  AS platform,
                    '{s("team")}'                AS team,
                    '{s("abuse_area")}'          AS abuse_area,
                    '{s("sub_abuse_area")}'      AS sub_abuse_area,
                    '{s("notes")}'               AS notes,
                    '{s("relevancy")}'           AS relevancy,
                    '{metadata_json}'            AS metadata,
                    current_timestamp()          AS added_at,
                    '{user}'                     AS added_by
                ) AS src
                ON t.url = src.url
                WHEN NOT MATCHED THEN INSERT *
            """)
            inserted += 1
        except Exception as e:
            errors.append(f"Row {i + 1}: {e}")

        progress.progress((i + 1) / total, text=f"Importing… {i + 1}/{total}")

    progress.empty()
    st.success(f"Imported {inserted} new sources. Skipped {skipped} empty rows.")
    if errors:
        with st.expander(f"{len(errors)} errors"):
            for e in errors:
                st.text(e)
    load_sources.clear()


def page_import_sources():
    st.title("Import Sources")

    tab_upload, tab_paste, tab_gsheet = st.tabs(["Upload CSV", "Paste Spreadsheet", "Google Sheets Link"])

    with tab_upload:
        uploaded = st.file_uploader("Upload a CSV file", type=["csv"])
        if uploaded:
            try:
                raw_df = pd.read_csv(uploaded)
                st.caption(f"{len(raw_df)} rows · {len(raw_df.columns)} columns")
                _render_import_ui(raw_df)
            except Exception as e:
                st.error(f"Could not parse file: {e}")

    with tab_paste:
        st.caption(
            "Paste tab-separated or CSV data from your spreadsheet. "
            "Include column headers in the first row."
        )
        pasted = st.text_area(
            "Paste data here",
            height=200,
            placeholder="Column1\tColumn2\t...\nvalue1\tvalue2\t...",
        )
        if pasted.strip():
            raw_df = _parse_paste(pasted)
            if raw_df is None or raw_df.empty:
                st.error("Could not parse the pasted data. Ensure it has headers and is tab-, comma-, or semicolon-separated.")
            else:
                st.caption(f"{len(raw_df)} rows · {len(raw_df.columns)} columns")
                _render_import_ui(raw_df)

    with tab_gsheet:
        st.caption(
            "Enter a Google Sheets URL. The sheet must be shared with the service account. "
            "If no tab is pre-selected in the URL, you can choose one after connecting."
        )
        gsheet_url = st.text_input(
            "Google Sheets URL",
            placeholder="https://docs.google.com/spreadsheets/d/.../.../edit#gid=0",
        )

        if gsheet_url.strip():
            try:
                spreadsheet_id, url_gid = _parse_gsheet_url(gsheet_url.strip())
            except ValueError as e:
                st.error(str(e))
                return

            if st.button("Connect & List Sheets"):
                try:
                    client = _get_gsheets_client()
                    spreadsheet = client.open_by_key(spreadsheet_id)
                    sheets = spreadsheet.worksheets()
                    st.session_state["gsheet_sheets"] = [(ws.id, ws.title) for ws in sheets]
                    st.session_state["gsheet_spreadsheet_id"] = spreadsheet_id
                    st.session_state["gsheet_url_gid"] = url_gid
                    st.session_state.pop("gsheet_df", None)
                except Exception as e:
                    st.error(f"Could not connect: {e}")

            if "gsheet_sheets" in st.session_state and st.session_state.get("gsheet_spreadsheet_id") == spreadsheet_id:
                sheets = st.session_state["gsheet_sheets"]
                url_gid = st.session_state.get("gsheet_url_gid")

                sheet_labels = [title for _, title in sheets]
                default_idx = next(
                    (i for i, (gid, _) in enumerate(sheets) if gid == url_gid), 0
                )
                selected_label = st.selectbox("Select tab", sheet_labels, index=default_idx)
                selected_gid = next(gid for gid, title in sheets if title == selected_label)

                if st.button("Load Tab"):
                    try:
                        client = _get_gsheets_client()
                        ws = client.open_by_key(spreadsheet_id).get_worksheet_by_id(selected_gid)
                        data = ws.get_all_values()
                        if not data:
                            st.warning("Sheet is empty.")
                        else:
                            raw_df = pd.DataFrame(data[1:], columns=data[0])
                            st.session_state["gsheet_df"] = raw_df
                    except Exception as e:
                        st.error(f"Could not load tab: {e}")

                if "gsheet_df" in st.session_state:
                    raw_df = st.session_state["gsheet_df"]
                    st.caption(f"{len(raw_df)} rows · {len(raw_df.columns)} columns")
                    _render_import_ui(raw_df)


# ---------------------------------------------------------------------------
# Page: Pending Review (scraper staging)
# ---------------------------------------------------------------------------

def page_pending_review():
    st.title("Pending Review")
    st.caption("Sources written by scrapers that have not yet been approved.")

    df = load_staging()

    if df.empty:
        st.success("No pending sources.")
        return

    for _, row in df.iterrows():
        with st.expander(f"{row.get('platform', '?')} — {row['url']}"):
            st.json(row.to_dict())
            c1, c2 = st.columns(2)
            if c1.button("Approve", key=f"approve_{row['url']}"):
                _approve_staged(row)
            if c2.button("Reject", key=f"reject_{row['url']}"):
                _reject_staged(row)


def _approve_staged(row):
    url = str(row["url"]).replace("'", "\\'")
    new_id = str(uuid.uuid4())
    user = current_user().replace("'", "\\'")

    def sr(field):
        return str(row.get(field, "") or "").replace("'", "\\'")

    try:
        run_statement(f"""
            MERGE INTO {SOURCES_TABLE} AS t
            USING (SELECT
                '{new_id}'          AS id,
                '{url}'             AS url,
                '{sr("platform")}'  AS platform,
                '{sr("team")}'      AS team,
                '{sr("abuse_area")}' AS abuse_area,
                '{sr("sub_abuse_area")}' AS sub_abuse_area,
                '{sr("notes")}'     AS notes,
                '{sr("relevancy")}' AS relevancy,
                '{sr("metadata")}' AS metadata,
                current_timestamp() AS added_at,
                '{user}'            AS added_by
            ) AS src
            ON t.url = src.url
            WHEN MATCHED THEN UPDATE SET t.added_at = current_timestamp()
            WHEN NOT MATCHED THEN INSERT *
        """)
        run_statement(f"DELETE FROM {STAGING_TABLE} WHERE url = '{url}'")
        st.success(f"Approved: {row['url']}")
        load_sources.clear()
        load_staging.clear()
    except Exception as e:
        st.error(f"Error: {e}")


def _reject_staged(row):
    url = str(row["url"]).replace("'", "\\'")
    try:
        run_statement(f"DELETE FROM {STAGING_TABLE} WHERE url = '{url}'")
        st.warning(f"Rejected: {row['url']}")
        load_staging.clear()
    except Exception as e:
        st.error(f"Error: {e}")


# ---------------------------------------------------------------------------
# Page: Run Scrapers
# ---------------------------------------------------------------------------

def page_run_scrapers():
    st.title("Run Scrapers")

    w = get_workspace_client()
    try:
        jobs = [j for j in w.jobs.list() if (j.settings.name or "").startswith("scraper_")]
    except Exception as e:
        st.error(f"Could not list jobs: {e}")
        return

    if not jobs:
        st.info("No jobs found with names starting with 'scraper_'.")
        return

    for job in jobs:
        job_id = job.job_id
        job_name = job.settings.name
        try:
            runs = list(w.jobs.list_runs(job_id=job_id, limit=1))
            if runs:
                last_run = runs[0]
                last_status = str(last_run.state.result_state or last_run.state.life_cycle_state or "UNKNOWN")
                last_time = (
                    datetime.fromtimestamp(last_run.start_time / 1000).strftime("%Y-%m-%d %H:%M")
                    if last_run.start_time else "—"
                )
            else:
                last_status, last_time = "Never run", "—"
        except Exception:
            last_status, last_time = "Unknown", "—"

        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        c1.write(f"**{job_name}**")
        c2.write(last_status)
        c3.write(last_time)
        if c4.button("Run Now", key=f"run_{job_id}"):
            with st.spinner(f"Triggering {job_name}…"):
                try:
                    run = w.jobs.run_now(job_id=job_id)
                    run_url = f"{w.config.host}/jobs/{job_id}/runs/{run.run_id}"
                    st.success(f"Started! [View run]({run_url})")
                except Exception as e:
                    st.error(f"Failed: {e}")


# ---------------------------------------------------------------------------
# Page: Dashboard
# ---------------------------------------------------------------------------

def page_dashboard():
    st.title("Dashboard")

    try:
        df = load_sources()
    except Exception as e:
        st.error(f"Could not load data: {e}")
        return

    if df.empty:
        st.info("No data yet.")
        return

    total = len(df)
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    added_this_week = len(df[df["added_at"].astype(str) >= cutoff]) if "added_at" in df.columns else 0
    platforms_count = df["platform"].nunique()

    k1, k2, k3 = st.columns(3)
    k1.metric("Total Sources", total)
    k2.metric("Added This Week", added_this_week)
    k3.metric("Platforms", platforms_count)

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("By Platform")
        st.bar_chart(df.groupby("platform").size().rename("count"))

    with col2:
        st.subheader("By Relevancy")
        rel = df[df["relevancy"].notna() & (df["relevancy"] != "")]
        if not rel.empty:
            st.bar_chart(rel.groupby("relevancy").size().rename("count"))
        else:
            st.info("No relevancy data yet.")

    st.subheader("Sources Added per Day (last 30 days)")
    if "added_at" in df.columns:
        df["added_date"] = pd.to_datetime(df["added_at"]).dt.date
        cutoff_date = (datetime.utcnow() - timedelta(days=30)).date()
        daily = df[df["added_date"] >= cutoff_date].groupby("added_date").size().rename("count")
        if not daily.empty:
            st.line_chart(daily)
        else:
            st.info("No sources added in the last 30 days.")


# ---------------------------------------------------------------------------
# Sidebar — Add New Source
# ---------------------------------------------------------------------------

def sidebar_add_source():
    st.sidebar.header("Add New Source")

    with st.sidebar.form("add_source_form", clear_on_submit=True):
        url = st.text_input("URL / Link *")
        platform_auto = st.checkbox("Auto-detect platform from URL", value=True)
        platform = st.selectbox("Platform", PLATFORMS, disabled=platform_auto)
        team = st.text_input("Team (e.g. CT, HS, CS)")
        abuse_area = st.text_input("Abuse Area (comma-separated)")
        sub_abuse_area = st.text_input("Sub Abuse Area (comma-separated)")
        relevancy = st.selectbox("Relevancy", [""] + RELEVANCY_OPTIONS)
        notes = st.text_area("Notes", height=80)
        submitted = st.form_submit_button("Add Source")

    if submitted:
        if not url.strip():
            st.sidebar.error("URL is required.")
            return

        resolved_platform = detect_platform_from_url(url) if platform_auto else platform
        new_id = str(uuid.uuid4())
        user = current_user().replace("'", "\\'")

        def s(v):
            return str(v or "").replace("'", "\\'")

        try:
            run_statement(f"""
                INSERT INTO {SOURCES_TABLE}
                  (id, url, platform, team, abuse_area, sub_abuse_area,
                   notes, relevancy, metadata, added_at, added_by)
                VALUES
                  ('{new_id}', '{s(url.strip())}', '{s(resolved_platform)}',
                   '{s(team)}', '{s(abuse_area)}', '{s(sub_abuse_area)}',
                   '{s(notes)}', '{s(relevancy)}', '{{}}',
                   current_timestamp(), '{user}')
            """)
            st.sidebar.success(f"Added: {url.strip()}")
            load_sources.clear()
        except Exception as e:
            st.sidebar.error(f"Insert failed: {e}")


def page_diagnostics():
    st.title("Diagnostics")

    st.subheader("Environment")
    st.code(
        f"DATABRICKS_HOST:         {os.environ.get('DATABRICKS_HOST', '(not set)')}\n"
        f"DATABRICKS_WAREHOUSE_ID: {os.environ.get('DATABRICKS_WAREHOUSE_ID', '(not set)')}\n"
        f"DATABRICKS_TOKEN:        {'(set)' if os.environ.get('DATABRICKS_TOKEN') else '(not set)'}\n"
        f"DATABRICKS_CLIENT_ID:    {'(set)' if os.environ.get('DATABRICKS_CLIENT_ID') else '(not set)'}\n"
    )

    st.subheader("SDK auth")
    try:
        wc = get_workspace_client()
        me = wc.current_user.me()
        st.success(f"WorkspaceClient OK — logged in as {me.user_name}")
    except Exception as e:
        st.error(f"WorkspaceClient failed: {e}")

    st.subheader("Token via SDK credential chain")
    try:
        headers = get_workspace_client().config.authenticate()
        token = headers.get("Authorization", "")
        if token:
            st.success(f"Token obtained: {token[:20]}...")
        else:
            st.error("No token returned")
    except Exception as e:
        st.error(f"authenticate() failed: {e}")

    st.subheader("SQL connection test")
    try:
        df = run_query("SELECT 1 AS ok")
        st.success(f"SQL connection OK: {df.to_dict()}")
    except Exception as e:
        st.error(f"SQL connection failed: {e}")

    st.subheader("Table access test")
    try:
        df = run_query(f"SELECT COUNT(*) AS cnt FROM {SOURCES_TABLE}")
        st.success(f"social_sources row count: {df['cnt'].iloc[0]}")
    except Exception as e:
        st.error(f"Table query failed: {e}")


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

PAGES = {
    "Sources Browser": page_sources_browser,
    "Import Sources":  page_import_sources,
    "Pending Review":  page_pending_review,
    "Run Scrapers":    page_run_scrapers,
    "Dashboard":       page_dashboard,
    "Diagnostics":     page_diagnostics,
}

st.set_page_config(page_title="Social Sources Platform", layout="wide")

selected_page = st.sidebar.selectbox("Navigate", list(PAGES.keys()))
sidebar_add_source()

PAGES[selected_page]()
