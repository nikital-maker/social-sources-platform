# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This App Does

Internal platform for managing social media sources (Telegram channels, Twitter accounts, TikTok profiles, etc.) discovered by Databricks scraper jobs or imported manually. Backed by Delta tables in Unity Catalog (`af_delivery_dev.data_collection` schema).

The app has two frontends: the original **Streamlit** app (`app.py`) and a new **FastAPI + React** rewrite (`backend/` + `frontend/`). Both share the same Delta tables and Databricks credentials.

## Commands

```bash
# --- FastAPI + React (new) ---
# Backend dev server
uvicorn backend.main:app --reload --port 8000

# Frontend dev server (proxies /api to localhost:8000)
cd frontend && npm run dev

# Build frontend for production
cd frontend && npm ci && npm run build

# Run production (serves built frontend from FastAPI)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4

# Deploy to Databricks Apps (uses startup.sh which builds frontend + runs uvicorn)
databricks apps deploy social-sources-platform --source-code-path .

# --- Streamlit (legacy) ---
streamlit run app.py

# --- Shared ---
# Create Delta tables (run once against a real Databricks workspace)
python setup_tables.py
```

Copy `.env.example` → `.env` and fill in `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_WAREHOUSE_ID` before running locally.

## Architecture

```
Databricks scraper Jobs (named scraper_*)          Manual import / UI forms
        │ write rows                                        │
        ▼                                                   │
  Delta: af_delivery_dev.data_collection.social_sources_staging
        │                                                   │
        ▼ dedup_job.py (scheduled Databricks Job)           │
  Delta: af_delivery_dev.data_collection.social_sources_*   │
        │ read / write via Statement Execution API          │
        ▼                                                   │
  backend/ (FastAPI)  ←── /api/* ───  frontend/ (React SPA)
  app.py (Streamlit, legacy)
```

### Delta Tables (`af_delivery_dev.data_collection`)

Per-team source tables (e.g. `social_sources_child_safety`, `social_sources_hate_speech`) — master deduplicated tables. Logical unique key on `url` enforced via MERGE, not a DB constraint (Delta Lake doesn't enforce UNIQUE). Columns: `id` (UUID), `url`, `platform`, `team`, `abuse_area`, `sub_abuse_area`, `notes`, `relevancy`, `metadata` (JSON string), `added_at`, `added_by`.

**`social_sources_staging`** — raw scraper feed. Same schema plus `scraper_name` and `raw_record` (raw JSON). Rows flow out via Approve (MERGE INTO target + DELETE from staging) or `dedup_job.py`.

**`gsheet_sync_config`** — stores Google Sheets auto-sync configurations. Each row represents one sheet+tab to periodically pull from. Columns: `id` (UUID), `spreadsheet_id`, `spreadsheet_url`, `spreadsheet_name`, `tab_title`, `gid`, `team`, `mapping_json`, `platform_override`, `manual_values_json`, `meta_mapping_json`, `sync_enabled` (boolean), `sync_interval_minutes`, `last_sync_at`, `last_sync_rows`, `last_sync_error`, `created_at`, `created_by`.

`TABLE_SUFFIX` env var appends a suffix (e.g. `_dev`) to all table names for dev/prod isolation.

### `backend/` — FastAPI API server

**`backend/main.py`** — FastAPI app. Mounts all routers under `/api`, serves the built React SPA (`frontend/dist/`) as a catch-all route, and provides `/api/health` and `/api/config` endpoints. Uses a lifespan hook to start/stop the background sync scheduler.

**`backend/config.py`** — Central configuration:
- `TEAMS` dict maps team display names → table name suffixes. Team selection determines which Delta table is queried.
- `STAGING_TABLE`, `SYNC_CONFIG_TABLE`, `PLATFORMS`, `RELEVANCY_OPTIONS`, `WORKFLOW_CONFIG` constants.
- `detect_platform_from_url()` — matches URL substrings (e.g. `t.me`, `telemetr.io` → Telegram). `detect_platform_from_column_name()` helpers.
- `get_sources_table(team)` resolves a team name to a fully-qualified Delta table path.

**`backend/dependencies.py`** — FastAPI dependencies: `get_current_user` (reads Databricks auth headers, falls back to SDK), `validate_team`.

**`backend/routers/`** — API route modules, all mounted at `/api`:
- `sources.py` (`/api/sources`) — CRUD for sources: list (paginated + filtered), add, delete, export CSV, dashboard stats, filter options.
- `staging.py` (`/api/staging`) — list pending staging rows, approve (MERGE + DELETE), reject (DELETE).
- `imports.py` (`/api/import`) — CSV upload, paste, Google Sheets import. Supports column mapping, platform auto-detect, metadata field mapping. The `/import/gsheet/sheets` endpoint returns `{name, tabs}` (spreadsheet title + worksheet list).
- `scrapers.py` (`/api/scrapers`) — list scraper jobs, trigger a run.
- `jobs.py` (`/api/jobs`) — Databricks job details, trigger, cancel, run status polling + SSE streaming (`/api/jobs/runs/{run_id}/stream`).
- `gsheets.py` (`/api/gsheets`) — Google Sheets integration endpoints.
- `sync_configs.py` (`/api/sync-configs`) — CRUD for Google Sheets auto-sync configurations: list, create, update (toggle, interval, mapping), delete, and manual trigger sync.

**`backend/services/`** — Business logic layer:
- `databricks_client.py` — `run_query()` → DataFrame, `run_statement()` → None, `get_workspace_client()`, `current_user()`. Uses Databricks Statement Execution API (not SQL connector).
- `sources.py` — `load_sources`, `insert_source`, `delete_sources_by_ids`, `build_filter_where`, `get_dashboard_data`, `get_filter_options`, multi-value filter helpers.
- `staging.py` — `load_staging` (LEFT ANTI JOIN), `approve_staged`, `reject_staged`.
- `import_logic.py` — `auto_map` (column name matching), `parse_paste`, `build_row_selects`, `do_import`, `execute_import` (batched MERGE in groups of 500).
- `gsheets.py` — Google Sheets client using `gspread` + service account.
- `scrapers.py` — list/trigger scraper jobs via WorkspaceClient.
- `job_monitor.py` — `get_run_status`, `get_job_details`, `trigger_job`, `cancel_run`, `build_task_graph_data`.
- `sync_config.py` — CRUD operations for `gsheet_sync_config` table, `run_sync_for_config()` reads a Google Sheet and MERGEs new rows.
- `sync_scheduler.py` — asyncio background loop that checks all enabled sync configs every 60s and triggers syncs when the configured interval has elapsed. Started/stopped via FastAPI lifespan hook.

**`backend/models/`** — Pydantic models:
- `source.py` — `Source`, `SourceCreate`, `SourcesPage`, `DeleteRequest`, `DashboardData`, `DailyCount`.
- `import_request.py` — `ColumnMapping`, `ImportRequest`, `ImportResult`.
- `job.py` — `ScraperJob`, `JobDetail`, `RunStatus`, `TaskStatus`, `WorkflowConfig`.
- `gsheet.py` — Google Sheets related models.
- `sync_config.py` — `SyncConfig`, `SyncConfigCreate`, `SyncConfigUpdate`, `SyncResult`.

### `frontend/` — React SPA (Vite + TypeScript)

**Stack:** React 19, React Router, TanStack React Query, Axios. Built with Vite. In dev, Vite proxies `/api` to `localhost:8000`.

**`frontend/src/App.tsx`** — Root component. Sets up React Query, React Router, ConfigContext, TeamContext, ToastProvider. Routes are team-scoped: `/:team/sources`, `/:team/import`, `/:team/connected-sheets`, `/:team/review`, `/:team/telegram`, `/:team/dashboard`, plus `/scrapers` and `/diagnostics`.

**`frontend/src/api/`** — API client modules (`client.ts`, `config.ts`, `sources.ts`, `staging.ts`, `scrapers.ts`, `jobs.ts`, `gsheets.ts`, `syncConfigs.ts`).

**`frontend/src/pages/`** — Page components: `SourcesBrowser`, `ImportSources`, `ConnectedSheets`, `PendingReview`, `RunScrapers`, `Dashboard`, `TelegramWorkflow`, `Diagnostics`. Both `SourcesBrowser` and `ConnectedSheets` have Refresh buttons that invalidate React Query caches.

**`frontend/src/components/`** — Shared components:
- `layout/AppShell.tsx` — main layout with sidebar navigation and team selector.
- `ui/` — reusable primitives: `Button`, `Card`, `Badge`, `Input`, `Spinner`, `Toast` (toast notification system with `ToastProvider` and `useToast` hook), `IntervalPicker` (minutes/hours/days/weeks/months interval selector, stores value as minutes).
- `jobs/TaskGraph.tsx` — DAG visualisation for Databricks job tasks.
- `shared/ErrorBanner.tsx` — error display component.

**`frontend/src/contexts/`** — `ConfigContext` (app-wide config from `/api/config`), `TeamContext` (selected team).

**`frontend/src/hooks/`** — `useJobMonitor.ts` (SSE-based job run polling).

### `app.py` — Legacy Streamlit entry point

Page functions are defined in `app.py`. Navigation is a sidebar `selectbox` driving a `PAGES` dict of page functions. The sidebar also renders the "Add New Source" form on every page.

**Important:** The Streamlit entry-point block (`st.set_page_config`, sidebar widgets, `PAGES[selected_page]()`) is guarded with `if __name__ == "__main__":`. This prevents those calls from executing when `app.py` is imported as a module by `modules/import_sources.py`, which would trigger a second `set_page_config` and crash.

**Do not put pages in the `pages/` directory.** Streamlit auto-discovers files there and adds them as top-level navigation tabs, creating a duplicate nav.

### `modules/import_sources.py` — Legacy Streamlit import page

Contains Import Sources page logic. Kept in `modules/` (not `pages/`) to avoid Streamlit auto-discovery. All imports from `app` are lazy to avoid circular-import / double-`set_page_config`.

### `startup.sh` — Databricks Apps entrypoint

Builds the frontend if `frontend/dist/` doesn't exist, then starts uvicorn with 4 workers on port 8000. Referenced by `app_fastapi.yaml`.

### `setup_tables.py`

One-time setup script. Drops and recreates all Delta tables in `af_delivery_dev.data_collection` (team source tables, staging, and gsheet_sync_config). **Note: it DROP TABLE first — do not re-run against a table with live data.**

### `dedup_job.py`

Meant to run as a Databricks Job Python task. MERGEs all staging rows into `social_sources` (insert-only, no updates on match), then deletes all staging rows.

## Environment / Credentials

- **Locally**: `python-dotenv` loads `.env`. If the file is missing the import silently no-ops — the Databricks SDK then falls back to `~/.databrickscfg` (DEFAULT profile).
- **On Databricks Apps**: credentials are injected automatically via the service principal; no `.env` needed.
- `current_user()` falls back to `"local_dev"` if `WorkspaceClient` can't reach the API (e.g. offline dev).

## Testing UI Changes

### FastAPI + React

```bash
# 1. Start backend
uvicorn backend.main:app --reload --port 8000 &

# 2. Start frontend dev server
cd frontend && npm run dev &

# 3. Open http://localhost:5173 in a browser
```

### Streamlit (legacy)

Always test UI changes locally with Playwright before pushing. Playwright (`playwright` pip package, chromium browser) is already installed.

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

**Playwright tips for Streamlit:**
- Streamlit selectboxes use `[data-baseweb='select']`, not native `<select>`. Click the box first, then click a `li` option.
- Sidebar selectboxes in order: 0 = Team, 1 = Navigate.
- Error banner selector: `.stException`

## Known Limitations / Watch-outs

- SQL in all write paths uses f-string interpolation with `.replace("'", "\\'")` escaping — not parameterised queries. Apply the same pattern for any new write paths.
- Scrapers must write to `social_sources_staging` with at minimum `url` populated; other fields are optional (NULLs are coalesced in `dedup_job.py`).
- Scraper jobs must be named with the `scraper_` prefix to appear on the Run Scrapers page.
- `setup_tables.py` has `DROP TABLE IF EXISTS` statements — safe to run only on a fresh/dev environment, not production.
- Google Sheets SA key fix: `_fix_sa_private_key` reformats single-line PEM keys (common when the key is stored without literal newlines).
- The `SourceCreate` model and `insert_source` service always store `'{}'` as metadata — the add-source API endpoint does not accept metadata input.
- **Connected Sheets → Import flow**: The "+ Connect Sheet" button on Connected Sheets navigates to `/:team/import?tab=gsheet&autosync=1`, pre-selecting the Google Sheets tab with auto-sync enabled. After a successful import with auto-sync, the user is redirected back to Connected Sheets where the new config appears.
- **Auto-sync interval**: Stored as `sync_interval_minutes` in the database. The `IntervalPicker` UI component converts between minutes/hours/days/weeks/months for display. Default is 1 day (1440 minutes).
- **`added_by` field**: On Databricks Apps, populated from `X-Databricks-User` header (actual logged-in user). Locally, falls back to the Databricks token owner or `"local_dev"`. Auto-sync background jobs use `current_user()` (service principal), not the person who configured the sync.
