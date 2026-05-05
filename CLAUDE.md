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

## Testing UI Changes

Always test UI changes locally with Playwright before pushing and redeploying. Playwright (`playwright` pip package, chromium browser) is already installed.

```bash
# 1. Start the app in the background
streamlit run app.py --server.headless true --server.port 8502 &
sleep 5

# 2. Run a Playwright smoke test (inline or as a script)
python3 << 'EOF'
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://localhost:8502", wait_until="networkidle", timeout=15000)
    time.sleep(3)

    # Navigate to a page via the sidebar selectbox
    page.locator("[data-baseweb='select']").nth(1).click()  # Navigate selectbox
    time.sleep(1)
    page.locator("li", has_text="Import Sources").click()
    time.sleep(4)

    errors = page.locator(".stException").all()
    print("ERRORS:" if errors else "OK - no errors")
    for e in errors:
        print(e.inner_text()[:400])

    browser.close()
EOF

# 3. Stop the local server
kill $(lsof -ti:8502)
```

**Playwright tips for this app:**
- Streamlit selectboxes use `[data-baseweb='select']`, not native `<select>`. Click the box first, then click a `li` option.
- Sidebar selectboxes in order: 0 = Team, 1 = Navigate.
- Error banner selector: `.stException`
- Spurious Streamlit page-nav links (from `pages/` auto-discovery): `[data-testid='stSidebarNavLink']` — should always be 0.

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

### `app.py` — Main Streamlit entry point

Page functions are defined in `app.py`. Navigation is a sidebar `selectbox` driving a `PAGES` dict of page functions. The sidebar also renders the "Add New Source" form on every page.

**Important:** The Streamlit entry-point block (`st.set_page_config`, sidebar widgets, `PAGES[selected_page]()`) is guarded with `if __name__ == "__main__":`. This prevents those calls from executing when `app.py` is imported as a module by `modules/import_sources.py`, which would trigger a second `set_page_config` and crash.

**Do not put pages in the `pages/` directory.** Streamlit auto-discovers files there and adds them as top-level navigation tabs, creating a duplicate nav. Page-specific logic that needs to import from `app.py` should live in `modules/` instead, using lazy imports (inside functions) to avoid the circular-import / double-`set_page_config` problem.

**Connection layer** — uses `databricks-sql-connector` (not Spark/DatabricksSession):
- `_db_conn_params()` — builds connection dict from env vars (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_WAREHOUSE_ID`).
- `run_query(sql)` → `pd.DataFrame` — opens a connection, executes, returns rows.
- `run_statement(sql)` → `None` — for DML (INSERT/MERGE/DELETE).
- `get_workspace_client()` — `@st.cache_resource`: one `WorkspaceClient` per process (used for job listing/triggering and Google Sheets file access).
- `load_sources()` / `load_staging()` — `@st.cache_data(ttl=60)`: DataFrames cached for 60 s. Always call `.clear()` on these after any write so the next render re-fetches.

**Pages:**
- `page_sources_browser` — reads `social_sources`, filters by platform/team/abuse_area/sub_abuse_area/relevancy/keyword, export to CSV.
- `page_import_sources` — thin wrapper that delegates to `modules/import_sources.py`. Three tabs: Upload CSV, Paste Spreadsheet, Google Sheets Link. Auto-maps columns, detects platform from URL, previews first 5 rows, then bulk-MERGEs via `_do_import`.
- `page_pending_review` — LEFT ANTI JOIN staging vs sources to show only truly new rows; Approve runs MERGE INTO + DELETE from staging; Reject just deletes from staging.
- `page_run_scrapers` — lists Databricks Jobs whose name starts with `scraper_` via `WorkspaceClient`, shows last run status/time, triggers `jobs.run_now()`.
- `page_dashboard` — KPI metrics (total, added this week, platform count) + bar charts by platform and relevancy + daily line chart for last 30 days.

### `modules/import_sources.py`

Contains all Import Sources page logic (`_render_import_ui`, `_do_import`, `page_import_sources`). Kept in `modules/` (not `pages/`) to avoid Streamlit auto-discovery. All imports from `app` are lazy — done inside functions via `_app()` helper — to avoid the circular import that would trigger `set_page_config` twice.

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
