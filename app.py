import uuid
from datetime import datetime, timedelta

import streamlit as st

# Load .env locally; silently skip if unavailable or missing
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from databricks.connect import DatabricksSession
from databricks.sdk import WorkspaceClient

# ---------------------------------------------------------------------------
# Spark session (cached globally for the process lifetime)
# ---------------------------------------------------------------------------

@st.cache_resource
def get_spark():
    return DatabricksSession.builder.getOrCreate()


@st.cache_resource
def get_workspace_client():
    return WorkspaceClient()


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_sources():
    spark = get_spark()
    return spark.table("main.social.sources").toPandas()


@st.cache_data(ttl=60)
def load_staging():
    spark = get_spark()
    return spark.sql(
        """
        SELECT s.*
        FROM main.social.sources_staging s
        LEFT ANTI JOIN main.social.sources m
          ON s.platform = m.platform AND s.identifier = m.identifier
        """
    ).toPandas()


def current_user() -> str:
    try:
        return get_workspace_client().current_user.me().user_name or "unknown"
    except Exception:
        return "local_dev"


# ---------------------------------------------------------------------------
# Page: Sources Browser
# ---------------------------------------------------------------------------

def page_sources_browser():
    st.title("Sources Browser")

    df = load_sources()

    if df.empty:
        st.info("No sources found. Add one using the sidebar form.")
        return

    # Summary row counts per platform
    counts = df.groupby("platform").size().reset_index(name="count")
    cols = st.columns(len(counts) + 1)
    cols[0].metric("Total", len(df))
    for i, row in counts.iterrows():
        cols[i + 1].metric(row["platform"], row["count"])

    st.divider()

    # Filters
    col1, col2, col3 = st.columns(3)
    platforms = ["All"] + sorted(df["platform"].dropna().unique().tolist())
    statuses = ["All"] + sorted(df["status"].dropna().unique().tolist())
    selected_platform = col1.selectbox("Platform", platforms)
    selected_status = col2.selectbox("Status", statuses)
    keyword = col3.text_input("Keyword in identifier")

    filtered = df.copy()
    if selected_platform != "All":
        filtered = filtered[filtered["platform"] == selected_platform]
    if selected_status != "All":
        filtered = filtered[filtered["status"] == selected_status]
    if keyword:
        filtered = filtered[
            filtered["identifier"].str.contains(keyword, case=False, na=False)
        ]

    st.dataframe(filtered, use_container_width=True)


# ---------------------------------------------------------------------------
# Page: Pending Review
# ---------------------------------------------------------------------------

def page_pending_review():
    st.title("Pending Review")
    st.caption("Sources discovered by scrapers that have not yet been approved.")

    df = load_staging()

    if df.empty:
        st.success("No pending sources to review.")
        return

    for _, row in df.iterrows():
        with st.expander(f"{row['platform']} — {row['identifier']}"):
            st.json(row.to_dict())
            c1, c2 = st.columns(2)

            if c1.button("Approve", key=f"approve_{row['identifier']}_{row['platform']}"):
                _approve_source(row)

            if c2.button("Reject", key=f"reject_{row['identifier']}_{row['platform']}"):
                _reject_source(row)


def _approve_source(row):
    spark = get_spark()
    try:
        new_id = str(uuid.uuid4())
        spark.sql(
            f"""
            MERGE INTO main.social.sources AS t
            USING (
              SELECT
                '{new_id}'            AS id,
                '{row['platform']}'   AS platform,
                '{row['identifier']}' AS identifier,
                '{row.get('display_name', '')}' AS display_name,
                '{row.get('metadata', '')}' AS metadata,
                '{row.get('status', 'active')}' AS status,
                current_timestamp()   AS added_at,
                current_timestamp()   AS last_seen_at,
                '{current_user()}'    AS added_by
            ) AS s
            ON t.platform = s.platform AND t.identifier = s.identifier
            WHEN MATCHED THEN
              UPDATE SET t.last_seen_at = current_timestamp()
            WHEN NOT MATCHED THEN
              INSERT *
            """
        )
        spark.sql(
            f"""
            DELETE FROM main.social.sources_staging
            WHERE platform = '{row['platform']}' AND identifier = '{row['identifier']}'
            """
        )
        st.success(f"Approved {row['identifier']}")
        load_sources.clear()
        load_staging.clear()
    except Exception as e:
        st.error(f"Error approving: {e}")


def _reject_source(row):
    spark = get_spark()
    try:
        spark.sql(
            f"""
            DELETE FROM main.social.sources_staging
            WHERE platform = '{row['platform']}' AND identifier = '{row['identifier']}'
            """
        )
        st.warning(f"Rejected {row['identifier']}")
        load_staging.clear()
    except Exception as e:
        st.error(f"Error rejecting: {e}")


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

        # Last run info
        try:
            runs = list(w.jobs.list_runs(job_id=job_id, limit=1))
            if runs:
                last_run = runs[0]
                last_status = (last_run.state.result_state or last_run.state.life_cycle_state or "UNKNOWN")
                last_time = datetime.fromtimestamp(last_run.start_time / 1000).strftime("%Y-%m-%d %H:%M") if last_run.start_time else "—"
            else:
                last_status, last_time = "Never run", "—"
        except Exception:
            last_status, last_time = "Unknown", "—"

        with st.container():
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
                        st.error(f"Failed to trigger job: {e}")


# ---------------------------------------------------------------------------
# Page: Dashboard
# ---------------------------------------------------------------------------

def page_dashboard():
    st.title("Dashboard")

    spark = get_spark()

    try:
        df = load_sources()
    except Exception as e:
        st.error(f"Could not load data: {e}")
        return

    if df.empty:
        st.info("No data yet.")
        return

    # KPI row
    total = len(df)
    active = len(df[df["status"] == "active"])
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    if "added_at" in df.columns:
        added_this_week = len(df[df["added_at"].astype(str) >= cutoff])
    else:
        added_this_week = 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Total Sources", total)
    k2.metric("Active Sources", active)
    k3.metric("Added This Week", added_this_week)

    st.divider()

    # Bar chart: sources per platform
    st.subheader("Sources per Platform")
    platform_counts = df.groupby("platform").size().rename("count")
    st.bar_chart(platform_counts)

    # Line chart: sources added per day (last 30 days)
    st.subheader("Sources Added per Day (last 30 days)")
    if "added_at" in df.columns:
        df["added_date"] = df["added_at"].astype("datetime64[ns]").dt.date
        cutoff_date = (datetime.utcnow() - timedelta(days=30)).date()
        daily = (
            df[df["added_date"] >= cutoff_date]
            .groupby("added_date")
            .size()
            .rename("count")
        )
        st.line_chart(daily)
    else:
        st.info("added_at column not available for trend chart.")


# ---------------------------------------------------------------------------
# Sidebar — Add New Source form
# ---------------------------------------------------------------------------

def sidebar_add_source():
    st.sidebar.header("Add New Source")

    with st.sidebar.form("add_source_form", clear_on_submit=True):
        platform = st.selectbox("Platform", ["Telegram", "Twitter", "TikTok"])
        identifier = st.text_input("Identifier (e.g. @handle or URL)")
        display_name = st.text_input("Display Name")
        status = st.selectbox("Status", ["active", "inactive"])
        submitted = st.form_submit_button("Add Source")

    if submitted:
        if not identifier.strip():
            st.sidebar.error("Identifier is required.")
            return

        spark = get_spark()
        new_id = str(uuid.uuid4())
        user = current_user()
        safe_identifier = identifier.strip().replace("'", "\\'")
        safe_display = display_name.strip().replace("'", "\\'")

        try:
            spark.sql(
                f"""
                INSERT INTO main.social.sources
                  (id, platform, identifier, display_name, metadata, status,
                   added_at, last_seen_at, added_by)
                VALUES
                  ('{new_id}', '{platform}', '{safe_identifier}',
                   '{safe_display}', '{{}}', '{status}',
                   current_timestamp(), current_timestamp(), '{user}')
                """
            )
            st.sidebar.success(f"Added {platform} source: {identifier}")
            load_sources.clear()
        except Exception as e:
            st.sidebar.error(f"Insert failed: {e}")


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

PAGES = {
    "Sources Browser": page_sources_browser,
    "Pending Review": page_pending_review,
    "Run Scrapers": page_run_scrapers,
    "Dashboard": page_dashboard,
}

st.set_page_config(page_title="Social Sources Platform", layout="wide")

selected_page = st.sidebar.selectbox("Navigate", list(PAGES.keys()))
sidebar_add_source()

PAGES[selected_page]()
