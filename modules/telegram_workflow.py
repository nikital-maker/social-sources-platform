import re
import time
from datetime import datetime

import pandas as pd
import streamlit as st

_POLL_INTERVAL_S = 15

_RUNNING_STATES = {"PENDING", "RUNNING", "TERMINATING", "QUEUED", "WAITING_FOR_RETRY", "BLOCKED"}
_DONE_STATES = {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}

# ---------------------------------------------------------------------------
# Pre-assigned team → workflow config
# Add more teams here as needed.
# ---------------------------------------------------------------------------
WORKFLOW_CONFIG = {
    "TEST": {
        "job_id":   "1013154753319258",
        "sheet_id": "1q6xjR1zFhf5WOL8qaS6yiwu4mhD-DL45xCNklf_SpOU",
        "job_url":  "https://dbc-34ec8d98-3f7f.cloud.databricks.com/jobs/1013154753319258",
        "sheet_url": "https://docs.google.com/spreadsheets/d/1q6xjR1zFhf5WOL8qaS6yiwu4mhD-DL45xCNklf_SpOU/edit",
    },
}


def _app():
    import app as _a
    return _a


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_state(state_str: str) -> str:
    """'RunLifeCycleState.RUNNING' → 'RUNNING'."""
    return state_str.split(".")[-1] if "." in state_str else state_str


_TASK_DOT_COLORS = {
    "SUCCESS":        ("#2d6a2d", "#a8e6a8"),
    "RUNNING":        ("#1a4a7a", "#7ec8f0"),
    "TERMINATING":    ("#1a4a7a", "#7ec8f0"),
    "PENDING":        ("#555555", "#cccccc"),
    "QUEUED":         ("#555555", "#cccccc"),
    "BLOCKED":        ("#555555", "#cccccc"),
    "WAITING_FOR_RETRY": ("#7a4a00", "#f5c97a"),
    "FAILED":         ("#7a1a1a", "#f0a0a0"),
    "INTERNAL_ERROR": ("#7a1a1a", "#f0a0a0"),
    "TIMEDOUT":       ("#7a1a1a", "#f0a0a0"),
    "SKIPPED":        ("#777777", "#e0e0e0"),
}

_TASK_PREFIX = {
    "SUCCESS": "✓ ", "RUNNING": "▶ ", "TERMINATING": "▶ ",
    "FAILED": "✗ ", "INTERNAL_ERROR": "✗ ", "TIMEDOUT": "✗ ",
}


def _get_run_status(run_id: int) -> dict:
    wc = _app().get_workspace_client()
    run = wc.jobs.get_run(run_id=run_id)
    state = run.state
    life_cycle = _clean_state(str(state.life_cycle_state or "UNKNOWN"))
    result = _clean_state(str(state.result_state)) if state.result_state else ""
    message = state.state_message or ""
    is_running = life_cycle in _RUNNING_STATES
    is_done = life_cycle in _DONE_STATES
    if not is_running and not is_done:
        is_running = True
    return {
        "life_cycle": life_cycle,
        "result": result,
        "message": message,
        "is_running": is_running,
        "is_done": is_done,
        "tasks": run.tasks or [],
    }


def _render_task_graph(tasks: list):
    if not tasks:
        return
    lines = [
        "digraph {",
        'rankdir=LR;',
        'graph [bgcolor="transparent", pad="0.3"];',
        'node [shape=box, style="filled,rounded", fontname="Arial", fontsize=11, margin="0.2,0.12"];',
        'edge [color="#888888", arrowsize=0.8];',
    ]
    for task in tasks:
        key = task.task_key or "unknown"
        lc = _clean_state(str(task.state.life_cycle_state or "PENDING")) if task.state else "PENDING"
        res = _clean_state(str(task.state.result_state)) if (task.state and task.state.result_state) else ""
        display = res if res else lc
        font_color, fill_color = _TASK_DOT_COLORS.get(display, ("#555555", "#cccccc"))
        prefix = _TASK_PREFIX.get(display, "")
        label = f"{prefix}{key}\\n{display}"
        lines.append(f'  "{key}" [label="{label}", fillcolor="{fill_color}", fontcolor="{font_color}"];')
    for task in tasks:
        for dep in (task.depends_on or []):
            lines.append(f'  "{dep.task_key}" -> "{task.task_key}";')
    lines.append("}")
    st.graphviz_chart("\n".join(lines), use_container_width=True)


def _sheet_df(ws) -> pd.DataFrame:
    data = ws.get_all_values()
    if not data:
        return pd.DataFrame()
    if len(data) == 1:
        return pd.DataFrame(columns=data[0])
    return pd.DataFrame(data[1:], columns=data[0])


def _clear_team_state(team: str):
    """Clear all workflow session state when switching teams."""
    prefix = f"tw_{team}_"
    for key in [k for k in st.session_state if k.startswith("tw_")]:
        del st.session_state[key]


# ---------------------------------------------------------------------------
# Spreadsheet section
# ---------------------------------------------------------------------------

@st.fragment
def _render_sheet_editor(df: pd.DataFrame, sheet_id: str, tab_title: str, tab_cache_key: str):
    editor_key = f"tw_editor_{tab_title}"
    edited = st.data_editor(
        df,
        use_container_width=True,
        height=350,
        num_rows="dynamic",
        key=editor_key,
    )
    st.caption(f"{len(df)} rows · {len(df.columns)} columns")

    if st.button("Save changes to sheet", key="tw_save_sheet", type="primary"):
        try:
            gc = _app()._get_gsheets_client()
            ws = gc.open_by_key(sheet_id).worksheet(tab_title)
            new_values = (
                [edited.columns.tolist()]
                + edited.fillna("").astype(str).values.tolist()
            )
            ws.update(values=new_values, range_name="A1")
            if ws.row_count > len(new_values):
                ws.resize(rows=len(new_values), cols=len(edited.columns))
            st.session_state[tab_cache_key] = edited.reset_index(drop=True)
            st.session_state.pop(editor_key, None)
            st.success(f"Saved {len(edited)} rows to '{tab_title}'.")
        except Exception as e:
            st.error(f"Save failed: {e}")


def _render_spreadsheet(team: str, sheet_id: str, job_is_running: bool):
    st.subheader("Spreadsheet")

    # Re-fetch from Google only on explicit Refresh or while job is running
    do_refresh = st.session_state.pop("tw_do_refresh_sheet", False) or job_is_running

    cache_key_meta = f"tw_sheet_meta_{sheet_id}"
    cache_key_data = f"tw_sheet_data_{sheet_id}"

    if do_refresh or cache_key_meta not in st.session_state:
        try:
            gc = _app()._get_gsheets_client()
            spreadsheet = gc.open_by_key(sheet_id)
            worksheets = spreadsheet.worksheets()
            st.session_state[cache_key_meta] = {
                "title": spreadsheet.title,
                "tabs": [{"title": ws.title, "id": ws.id} for ws in worksheets],
                "refreshed_at": datetime.now().strftime("%H:%M:%S"),
            }
            st.session_state.pop(cache_key_data, None)
        except Exception as e:
            st.error(f"Could not open spreadsheet: {e}")
            return

    meta = st.session_state[cache_key_meta]
    tab_names = [t["title"] for t in meta["tabs"]]

    col_title, col_refresh = st.columns([5, 1])
    refresh_note = f" · auto-refreshing every {_POLL_INTERVAL_S}s" if job_is_running else ""
    col_title.markdown(
        f"**{meta['title']}** · {len(tab_names)} tab(s) · loaded {meta['refreshed_at']}{refresh_note}"
    )
    if col_refresh.button("Refresh", key="tw_refresh_btn"):
        st.session_state["tw_do_refresh_sheet"] = True
        st.rerun()

    sel_idx = st.selectbox(
        "Tab",
        range(len(tab_names)),
        format_func=lambda i: tab_names[i],
        key="tw_sel_tab",
    )
    tab_title = tab_names[sel_idx]

    with st.popover("Rename tab"):
        new_name = st.text_input("New name", value=tab_title, key="tw_rename_val")
        if st.button("Save rename", key="tw_rename_btn"):
            try:
                gc = _app()._get_gsheets_client()
                ws = gc.open_by_key(sheet_id).worksheet(tab_title)
                ws.update_title(new_name)
                st.success(f"Renamed to '{new_name}'")
                st.session_state["tw_do_refresh_sheet"] = True
                st.rerun()
            except Exception as e:
                st.error(f"Rename failed: {e}")

    tab_cache_key = f"{cache_key_data}_{tab_title}"
    if do_refresh or tab_cache_key not in st.session_state:
        try:
            gc = _app()._get_gsheets_client()
            ws = gc.open_by_key(sheet_id).worksheet(tab_title)
            st.session_state[tab_cache_key] = _sheet_df(ws)
        except Exception as e:
            st.error(f"Could not read tab: {e}")
            return

    df = st.session_state[tab_cache_key]

    if df.empty and len(df.columns) == 0:
        st.info("Tab is empty.")
        return

    _render_sheet_editor(df, sheet_id, tab_title, tab_cache_key)


# ---------------------------------------------------------------------------
# Job control section
# ---------------------------------------------------------------------------

def _task_type_and_path(task) -> tuple[str, str]:
    if task.notebook_task:
        return "Notebook", task.notebook_task.notebook_path or ""
    if getattr(task, "spark_python_task", None):
        return "Python", task.spark_python_task.python_file or ""
    if getattr(task, "python_wheel_task", None):
        t = task.python_wheel_task
        return "Python Wheel", getattr(t, "entry_point", "") or getattr(t, "package_name", "")
    if getattr(task, "spark_jar_task", None):
        return "JAR", task.spark_jar_task.main_class_name or ""
    if getattr(task, "sql_task", None):
        return "SQL", ""
    if getattr(task, "run_job_task", None):
        return "Run Job", str(getattr(task.run_job_task, "job_id", ""))
    if getattr(task, "pipeline_task", None):
        return "Pipeline", str(getattr(task.pipeline_task, "pipeline_id", ""))
    return "Unknown", ""


def _render_job_details(job):
    with st.expander("Job details", expanded=False):
        settings = job.settings
        params = getattr(settings, "parameters", None) or []
        if params:
            st.markdown("**Parameters**")
            st.dataframe(
                pd.DataFrame([{"Name": p.name, "Default": getattr(p, "default", "")} for p in params]),
                use_container_width=True,
                hide_index=True,
            )
        tasks = settings.tasks or []
        if tasks:
            st.markdown(f"**Tasks** ({len(tasks)})")
            rows = []
            for t in tasks:
                task_type, path = _task_type_and_path(t)
                nb_params = ""
                if t.notebook_task and t.notebook_task.base_parameters:
                    nb_params = ", ".join(f"{k}={v}" for k, v in t.notebook_task.base_parameters.items())
                rows.append({
                    "Task": t.task_key,
                    "Type": task_type,
                    "Path / Entry": path,
                    "Params": nb_params,
                    "Depends on": ", ".join(d.task_key for d in (t.depends_on or [])),
                    "Cluster": (
                        getattr(t, "job_cluster_key", None)
                        or getattr(t, "existing_cluster_id", None)
                        or "default"
                    ),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if not params and not tasks:
            st.info("No tasks or parameters found.")


def _render_job_control(team: str, job_id: str, job_url: str) -> bool:
    """Render job control. Returns True if job is currently running."""
    st.subheader("Job Control")

    wc = _app().get_workspace_client()

    try:
        job = wc.jobs.get(job_id=int(job_id))
        job_name = job.settings.name or f"Job {job_id}"
    except Exception as e:
        st.error(f"Could not fetch job info: {e}")
        return False

    try:
        runs = list(wc.jobs.list_runs(job_id=int(job_id), limit=1))
        last_time = (
            datetime.fromtimestamp(runs[0].start_time / 1000).strftime("%Y-%m-%d %H:%M")
            if runs and runs[0].start_time else "Never"
        )
    except Exception:
        last_time = "Unknown"

    st.markdown(f"**{job_name}**")
    st.caption(f"Last run: {last_time}")

    _render_job_details(job)
    st.divider()

    active_run_id = st.session_state.get("tw_active_run_id")
    if not active_run_id:
        try:
            active_runs = list(wc.jobs.list_runs(job_id=int(job_id), active_only=True, limit=1))
            if active_runs:
                st.session_state["tw_active_run_id"] = active_runs[0].run_id
                active_run_id = active_runs[0].run_id
        except Exception:
            pass

    if active_run_id:
        return _render_run_status(active_run_id, job_id)

    if st.button("Run Now", type="primary", key="tw_run_btn"):
        try:
            triggered = wc.jobs.run_now(job_id=int(job_id))
            st.session_state["tw_active_run_id"] = triggered.run_id
            st.session_state["tw_run_start"] = datetime.now().isoformat()
            st.rerun()
        except Exception as e:
            st.error(f"Failed to trigger job: {e}")

    return False


def _render_run_status(run_id: int, job_id: str) -> bool:
    """Render live run status. Returns True if still running."""
    wc = _app().get_workspace_client()
    run_url = f"{wc.config.host}/jobs/{job_id}/runs/{run_id}"
    start_iso = st.session_state.get("tw_run_start", "")

    try:
        status = _get_run_status(run_id)
    except Exception as e:
        st.error(f"Could not poll run {run_id}: {e}")
        if st.button("Clear", key="tw_clear_err"):
            st.session_state.pop("tw_active_run_id", None)
            st.rerun()
        return False

    life_cycle = status["life_cycle"]
    result = status["result"]
    is_running = status["is_running"]

    tasks = status.get("tasks", [])

    if is_running:
        elapsed_s = ""
        if start_iso:
            elapsed = datetime.now() - datetime.fromisoformat(start_iso)
            elapsed_s = f" · {int(elapsed.total_seconds())}s elapsed"

        st.info(f"**{life_cycle}**{elapsed_s}")
        st.markdown(f"[View run in Databricks]({run_url})")
        _render_task_graph(tasks)

        col_stop_track, col_stop_job = st.columns(2)
        if col_stop_track.button("Stop tracking", key="tw_stop"):
            st.session_state.pop("tw_active_run_id", None)
            st.rerun()
        if col_stop_job.button("⏹ Stop job", key="tw_cancel_job", type="secondary"):
            try:
                wc.jobs.cancel_run(run_id=run_id)
                st.toast("Job cancellation requested — waiting for it to stop…", icon="⏹")
            except Exception as e:
                st.error(f"Could not cancel job: {e}")
        st.caption(f"Polling every {_POLL_INTERVAL_S}s")

        with st.spinner(f"Next check in {_POLL_INTERVAL_S}s…"):
            time.sleep(_POLL_INTERVAL_S)
        st.rerun()

    else:
        if st.session_state.get("tw_notified_run_id") != run_id:
            icon = "✅" if result == "SUCCESS" else "❌"
            st.toast(f"Job {result or life_cycle}", icon=icon)
            st.session_state["tw_notified_run_id"] = run_id

        if result == "SUCCESS":
            st.success(f"Completed successfully. [View run]({run_url})")
        else:
            label = result if result else life_cycle
            msg = f" — {status['message']}" if status["message"] else ""
            st.error(f"Finished: {label}{msg}. [View run]({run_url})")

        _render_task_graph(tasks)

        if st.button("Clear & run again", key="tw_clear_done"):
            st.session_state.pop("tw_active_run_id", None)
            st.session_state.pop("tw_run_start", None)
            st.session_state.pop("tw_notified_run_id", None)
            st.rerun()

    return False


# ---------------------------------------------------------------------------
# Page entry point
# ---------------------------------------------------------------------------

def page_telegram_workflow():
    st.title("Telegram Workflow")

    team = _app().get_selected_team()
    config = WORKFLOW_CONFIG.get(team)

    # Clear state when team changes
    if st.session_state.get("tw_active_team") != team:
        for key in [k for k in st.session_state if k.startswith("tw_")]:
            del st.session_state[key]
        st.session_state["tw_active_team"] = team

    if not config:
        st.info(
            f"No workflow is configured for team **{team}**. "
            "Ask an admin to add it to `WORKFLOW_CONFIG` in `modules/telegram_workflow.py`."
        )
        return

    st.caption(f"Team: **{team}** · [Open spreadsheet]({config['sheet_url']}) · [Open job]({config['job_url']})")
    st.divider()

    right_col, left_col = st.columns([2, 3], gap="large")

    with right_col:
        job_is_running = _render_job_control(team, config["job_id"], config["job_url"])

    with left_col:
        _render_spreadsheet(team, config["sheet_id"], job_is_running)
