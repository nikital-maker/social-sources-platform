# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This App Does

Internal platform for managing social media sources (Telegram channels, Twitter accounts, TikTok profiles) discovered by Databricks scraper jobs. Built as a Databricks App (Streamlit) backed by Delta tables in Unity Catalog (`main.social` schema).

## Commands

```bash
# Run locally (requires .env with valid Databricks credentials)
streamlit run app.py

# Create Delta tables (run once against a real Databricks workspace)
python setup_tables.py

# Deploy to Databricks Apps
databricks apps deploy social-sources-platform --source-code-path .
databricks apps open social-sources-platform
```

Copy `.env.example` → `.env` and fill in `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_WAREHOUSE_ID` before running locally.

## Architecture

```
Databricks scraper Jobs (named scraper_*)
        │ write rows
        ▼
  Delta: main.social.sources_staging
        │
        ▼ dedup_job.py (scheduled Databricks Job) or manual Approve button
  Delta: main.social.sources
        │ read / write
        ▼
  app.py (Streamlit, single file)
```

### Delta Tables (`main.social`)

**`sources`** — master deduplicated table. Logical unique key on `(platform, identifier)` enforced via MERGE, not a DB constraint (Delta Lake doesn't enforce UNIQUE). Has `id` (UUID), `platform`, `identifier`, `display_name`, `metadata` (JSON string), `status`, `added_at`, `last_seen_at`, `added_by`.

**`sources_staging`** — raw scraper feed. Same schema plus `scraper_name` and `raw_record` (raw JSON). Rows flow out via Approve (MERGE INTO sources) or `dedup_job.py`.

### `app.py` — Single-file Streamlit app

All pages live in one file. Navigation is a sidebar `selectbox` driving a `PAGES` dict of page functions. The sidebar also renders the "Add New Source" form on every page.

**Session/connection management:**
- `get_spark()` — `@st.cache_resource`: one `DatabricksSession` per process.
- `get_workspace_client()` — `@st.cache_resource`: one `WorkspaceClient` per process.
- `load_sources()` / `load_staging()` — `@st.cache_data(ttl=60)`: DataFrames cached for 60 s. Always call `.clear()` on these after any write so the next render re-fetches.

**Pages:**
- `page_sources_browser` — reads `main.social.sources`, platform/status/keyword filters, per-platform metric row.
- `page_pending_review` — LEFT ANTI JOIN staging vs sources to show only truly new rows; Approve runs a MERGE INTO + DELETE from staging; Reject just deletes from staging.
- `page_run_scrapers` — lists Databricks Jobs whose name starts with `scraper_` via `WorkspaceClient`, triggers `jobs.run_now()`.
- `page_dashboard` — KPI metrics + `st.bar_chart` / `st.line_chart` from `load_sources()`.

**`sidebar_add_source()`** — always rendered; inserts directly into `main.social.sources` with a generated UUID.

### `setup_tables.py`

One-time setup script. Creates `main.social` schema and both Delta tables if they don't exist. Safe to re-run (uses `CREATE TABLE IF NOT EXISTS`).

### `dedup_job.py`

Meant to run as a Databricks Job Python task (no local execution). Uses `DatabricksSession` which auto-connects inside a Databricks cluster. MERGEs all staging rows into sources, then deletes all staging rows. Prints insert/update counts from `DESCRIBE HISTORY`.

## Environment / Credentials

- **Locally**: `python-dotenv` loads `.env`. If the file is missing the import silently no-ops — the Databricks SDK then falls back to `~/.databrickscfg` (DEFAULT profile).
- **On Databricks Apps**: credentials are injected automatically via the service principal; no `.env` needed.
- `current_user()` falls back to `"local_dev"` if `WorkspaceClient` can't reach the API (e.g. offline dev).

## Known Limitations / Watch-outs

- SQL in `_approve_source`, `_reject_source`, and `sidebar_add_source` uses f-string interpolation with basic `'` escaping — not parameterised queries. If adding new write paths, apply the same `replace("'", "\\'")` pattern or switch to parameterised Spark SQL.
- Scrapers must write to `main.social.sources_staging` with at minimum `platform` and `identifier` populated; other fields are optional (NULLs are coalesced in `dedup_job.py`).
- Scraper jobs must be named with the `scraper_` prefix to appear on the Run Scrapers page.
