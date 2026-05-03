# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This App Does

Internal platform for managing social media sources (Telegram channels, Twitter accounts, TikTok profiles, etc.) discovered by Databricks scraper jobs or imported manually. Built as a Databricks App (Streamlit) backed by Delta tables in Unity Catalog (`af_delivery_dev.data_collection` schema).

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
Databricks scraper Jobs (named scraper_*)          Manual import / sidebar form
        │ write rows                                        │
        ▼                                                   │
  Delta: af_delivery_dev.data_collection.social_sources_staging
        │
        ▼ dedup_job.py (scheduled Databricks Job) or manual Approve button
  Delta: af_delivery_dev.data_collection.social_sources
        │ read / write
        ▼
  app.py (Streamlit, single file)
```

### Delta Tables (`af_delivery_dev.data_collection`)

**`social_sources`** — master deduplicated table. Logical unique key on `url` enforced via MERGE, not a DB constraint (Delta Lake doesn't enforce UNIQUE). Columns: `id` (UUID), `url`, `platform`, `team`, `abuse_area`, `sub_abuse_area`, `notes`, `relevancy`, `metadata` (JSON string), `added_at`, `added_by`.

**`social_sources_staging`** — raw scraper feed. Same schema plus `scraper_name` and `raw_record` (raw JSON). Rows flow out via Approve (MERGE INTO social_sources + DELETE from staging) or `dedup_job.py`.

### `app.py` — Single-file Streamlit app

All pages live in one file. Navigation is a sidebar `selectbox` driving a `PAGES` dict of page functions. The sidebar also renders the "Add New Source" form on every page.

**Connection layer** — uses `databricks-sql-connector` (not Spark/DatabricksSession):
- `_db_conn_params()` — builds connection dict from env vars (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_WAREHOUSE_ID`).
- `run_query(sql)` → `pd.DataFrame` — opens a connection, executes, returns rows.
- `run_statement(sql)` → `None` — for DML (INSERT/MERGE/DELETE).
- `get_workspace_client()` — `@st.cache_resource`: one `WorkspaceClient` per process (used for job listing/triggering and Google Sheets file access).
- `load_sources()` / `load_staging()` — `@st.cache_data(ttl=60)`: DataFrames cached for 60 s. Always call `.clear()` on these after any write so the next render re-fetches.

**Pages:**
- `page_sources_browser` — reads `social_sources`, filters by platform/team/abuse_area/sub_abuse_area/relevancy/keyword, export to CSV.
- `page_import_sources` — three tabs: Upload CSV, Paste Spreadsheet, Google Sheets Link. Auto-maps columns, detects platform from URL, previews first 5 rows, then bulk-MERGEs via `_do_import`.
- `page_pending_review` — LEFT ANTI JOIN staging vs sources to show only truly new rows; Approve runs MERGE INTO + DELETE from staging; Reject just deletes from staging.
- `page_run_scrapers` — lists Databricks Jobs whose name starts with `scraper_` via `WorkspaceClient`, shows last run status/time, triggers `jobs.run_now()`.
- `page_dashboard` — KPI metrics (total, added this week, platform count) + bar charts by platform and relevancy + daily line chart for last 30 days.

**`sidebar_add_source()`** — always rendered; inserts directly into `social_sources` with a generated UUID. Supports auto-detect platform from URL.

**Platform detection:**
- `detect_platform_from_url(url)` — matches URL substrings against `_PLATFORM_URL_PATTERNS`.
- `detect_platform_from_column_name(col)` — hints platform from CSV column name keywords.

**Multi-value filter helpers** (`get_multivalue_options`, `multivalue_mask`) — handle comma-separated values in `team`, `abuse_area`, `sub_abuse_area`, `relevancy` columns.

**Google Sheets integration** (`_get_gsheets_client`):
- Uses `gspread` + `oauth2client` with a service account JSON file.
- Looks for the SA file at `GOOGLE_SERVICE_ACCOUNT_PATH` env var, falling back to a hardcoded Workspace path.
- On Databricks Apps (where `/Workspace` isn't mounted as a filesystem path), reads the file via `WorkspaceClient.workspace.export()`.

### `setup_tables.py`

One-time setup script. Drops and recreates both Delta tables in `af_delivery_dev.data_collection`. **Note: it DROP TABLE first — do not re-run against a table with live data.**

### `dedup_job.py`

Meant to run as a Databricks Job Python task. Uses `databricks-sql-connector` with env vars (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_WAREHOUSE_ID`). MERGEs all staging rows into `social_sources` (insert-only, no updates on match), then deletes all staging rows. Prints row counts before/after.

## Environment / Credentials

- **Locally**: `python-dotenv` loads `.env`. If the file is missing the import silently no-ops — the Databricks SDK then falls back to `~/.databrickscfg` (DEFAULT profile).
- **On Databricks Apps**: credentials are injected automatically via the service principal; no `.env` needed.
- `current_user()` falls back to `"local_dev"` if `WorkspaceClient` can't reach the API (e.g. offline dev).

## Known Limitations / Watch-outs

- SQL in all write paths (`_do_import`, `_approve_staged`, `_reject_staged`, `sidebar_add_source`) uses f-string interpolation with `.replace("'", "\\'")` escaping — not parameterised queries. Apply the same pattern for any new write paths.
- Scrapers must write to `social_sources_staging` with at minimum `url` populated; other fields are optional (NULLs are coalesced in `dedup_job.py`).
- Scraper jobs must be named with the `scraper_` prefix to appear on the Run Scrapers page.
- `setup_tables.py` has `DROP TABLE IF EXISTS` statements — safe to run only on a fresh/dev environment, not production.
- Google Sheets SA key fix: `_fix_sa_private_key` reformats single-line PEM keys (common when the key is stored without literal newlines).
