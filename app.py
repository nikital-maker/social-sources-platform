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

_SCHEMA = "af_delivery_dev.data_collection"
STAGING_TABLE = f"{_SCHEMA}.social_sources_staging"

TEAMS = {
    "Child Safety":       "social_sources_child_safety",
    "Human Exploitation": "social_sources_human_exploitation",
    "Hate Speech":        "social_sources_hate_speech",
    "NCII":               "social_sources_ncii",
    "Illegal Goods":      "social_sources_illegal_goods",
}

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
# Team / table routing
# ---------------------------------------------------------------------------

def get_selected_team() -> str:
    return st.session_state.get("selected_team", list(TEAMS.keys())[0])


def get_sources_table() -> str:
    return f"{_SCHEMA}.{TEAMS[get_selected_team()]}"


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
def load_sources(table: str) -> pd.DataFrame:
    return run_query(f"SELECT * FROM {table} ORDER BY added_at DESC")


@st.cache_data(ttl=60)
def load_staging(sources_table: str) -> pd.DataFrame:
    return run_query(
        f"""
        SELECT s.*
        FROM {STAGING_TABLE} s
        LEFT ANTI JOIN {sources_table} m ON s.url = m.url
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
    run_statement(f"DELETE FROM {get_sources_table()} WHERE id IN ({escaped})")


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
    st.title(f"Sources Browser — {get_selected_team()}")

    try:
        df = load_sources(get_sources_table())
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
# Page: Import Sources (logic lives in pages/import_sources.py)
# ---------------------------------------------------------------------------


def page_import_sources():
    from pages._import_sources import page_import_sources as _impl
    _impl()


# ---------------------------------------------------------------------------
# Page: Pending Review (scraper staging)
# ---------------------------------------------------------------------------

def page_pending_review():
    st.title("Pending Review")
    st.caption(f"Approving into: **{get_selected_team()}** table. Sources written by scrapers that have not yet been approved.")

    df = load_staging(get_sources_table())

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
    target_table = get_sources_table()

    def sr(field):
        return str(row.get(field, "") or "").replace("'", "\\'")

    try:
        run_statement(f"""
            MERGE INTO {target_table} AS t
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
    st.title(f"Dashboard — {get_selected_team()}")

    try:
        df = load_sources(get_sources_table())
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
    team = get_selected_team()
    st.sidebar.header(f"Add Source → {team}")

    with st.sidebar.form("add_source_form", clear_on_submit=True):
        url = st.text_input("URL / Link *")
        platform_auto = st.checkbox("Auto-detect platform from URL", value=True)
        platform = st.selectbox("Platform", PLATFORMS, disabled=platform_auto)
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
        target_table = get_sources_table()

        def s(v):
            return str(v or "").replace("'", "\\'")

        try:
            run_statement(f"""
                INSERT INTO {target_table}
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
        table = get_sources_table()
        df = run_query(f"SELECT COUNT(*) AS cnt FROM {table}")
        st.success(f"{table} row count: {df['cnt'].iloc[0]}")
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

st.sidebar.selectbox("Team", list(TEAMS.keys()), key="selected_team")
st.sidebar.divider()
selected_page = st.sidebar.selectbox("Navigate", list(PAGES.keys()))
sidebar_add_source()

PAGES[selected_page]()
