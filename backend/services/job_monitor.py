from datetime import datetime

from backend.services.databricks_client import get_workspace_client

_RUNNING_STATES = {"PENDING", "RUNNING", "TERMINATING", "QUEUED", "WAITING_FOR_RETRY", "BLOCKED"}
_DONE_STATES = {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}

_TASK_DOT_COLORS: dict[str, tuple[str, str]] = {
    "SUCCESS":           ("#2d6a2d", "#a8e6a8"),
    "RUNNING":           ("#1a4a7a", "#7ec8f0"),
    "TERMINATING":       ("#1a4a7a", "#7ec8f0"),
    "PENDING":           ("#555555", "#cccccc"),
    "QUEUED":            ("#555555", "#cccccc"),
    "BLOCKED":           ("#555555", "#cccccc"),
    "WAITING_FOR_RETRY": ("#7a4a00", "#f5c97a"),
    "FAILED":            ("#7a1a1a", "#f0a0a0"),
    "INTERNAL_ERROR":    ("#7a1a1a", "#f0a0a0"),
    "TIMEDOUT":          ("#7a1a1a", "#f0a0a0"),
    "SKIPPED":           ("#777777", "#e0e0e0"),
}


def _clean_state(state_str: str) -> str:
    return state_str.split(".")[-1] if "." in state_str else state_str


def get_run_status(run_id: int) -> dict:
    wc = get_workspace_client()
    run = wc.jobs.get_run(run_id=run_id)
    state = run.state
    life_cycle = _clean_state(str(state.life_cycle_state or "UNKNOWN"))
    result = _clean_state(str(state.result_state)) if state.result_state else ""
    message = state.state_message or ""
    is_running = life_cycle in _RUNNING_STATES
    is_done = life_cycle in _DONE_STATES
    if not is_running and not is_done:
        is_running = True

    tasks = build_task_graph_data(run.tasks or [])

    return {
        "run_id": run_id,
        "life_cycle": life_cycle,
        "result": result,
        "message": message,
        "is_running": is_running,
        "is_done": is_done,
        "tasks": tasks,
    }


def build_task_graph_data(tasks: list) -> list[dict]:
    result = []
    for task in tasks:
        key = task.task_key or "unknown"
        lc = (
            _clean_state(str(task.state.life_cycle_state or "PENDING"))
            if task.state
            else "PENDING"
        )
        res = (
            _clean_state(str(task.state.result_state))
            if (task.state and task.state.result_state)
            else ""
        )
        display = res if res else lc
        font_color, fill_color = _TASK_DOT_COLORS.get(display, ("#555555", "#cccccc"))
        depends_on = [d.task_key for d in (task.depends_on or [])]

        result.append(
            {
                "key": key,
                "life_cycle": lc,
                "result": res,
                "display_state": display,
                "font_color": font_color,
                "fill_color": fill_color,
                "depends_on": depends_on,
            }
        )
    return result


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


def get_job_details(job_id: int) -> dict:
    wc = get_workspace_client()
    job = wc.jobs.get(job_id=job_id)
    settings = job.settings
    name = settings.name or f"Job {job_id}"

    params = [
        {"name": p.name, "default": getattr(p, "default", "")}
        for p in (getattr(settings, "parameters", None) or [])
    ]

    tasks_detail = []
    for t in (settings.tasks or []):
        task_type, path = _task_type_and_path(t)
        nb_params = ""
        if t.notebook_task and t.notebook_task.base_parameters:
            nb_params = ", ".join(f"{k}={v}" for k, v in t.notebook_task.base_parameters.items())
        tasks_detail.append(
            {
                "key": t.task_key,
                "type": task_type,
                "path": path,
                "params": nb_params,
                "depends_on": [d.task_key for d in (t.depends_on or [])],
                "cluster": (
                    getattr(t, "job_cluster_key", None)
                    or getattr(t, "existing_cluster_id", None)
                    or "default"
                ),
            }
        )

    last_run_at = None
    try:
        runs = list(wc.jobs.list_runs(job_id=job_id, limit=1))
        if runs and runs[0].start_time:
            last_run_at = datetime.fromtimestamp(runs[0].start_time / 1000).isoformat()
    except Exception:
        pass

    active_run_id = None
    try:
        active_runs = list(wc.jobs.list_runs(job_id=job_id, active_only=True, limit=1))
        if active_runs:
            active_run_id = active_runs[0].run_id
    except Exception:
        pass

    return {
        "job_id": job_id,
        "name": name,
        "last_run_at": last_run_at,
        "active_run_id": active_run_id,
        "parameters": params,
        "tasks": tasks_detail,
    }


def trigger_job(job_id: int) -> dict:
    wc = get_workspace_client()
    run = wc.jobs.run_now(job_id=job_id)
    run_url = f"{wc.config.host}/jobs/{job_id}/runs/{run.run_id}"
    return {"run_id": run.run_id, "run_url": run_url}


def cancel_run(run_id: int) -> None:
    wc = get_workspace_client()
    wc.jobs.cancel_run(run_id=run_id)
