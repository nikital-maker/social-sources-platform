from datetime import datetime

from backend.services.databricks_client import get_workspace_client


def list_scraper_jobs() -> list[dict]:
    wc = get_workspace_client()
    jobs = [j for j in wc.jobs.list() if (j.settings.name or "").startswith("scraper_")]

    result = []
    for job in jobs:
        job_id = job.job_id
        job_name = job.settings.name or f"job_{job_id}"
        try:
            runs = list(wc.jobs.list_runs(job_id=job_id, limit=1))
            if runs:
                last_run = runs[0]
                last_status = str(
                    last_run.state.result_state
                    or last_run.state.life_cycle_state
                    or "UNKNOWN"
                ).split(".")[-1]
                last_run_at = (
                    datetime.fromtimestamp(last_run.start_time / 1000).isoformat()
                    if last_run.start_time
                    else None
                )
            else:
                last_status = "Never run"
                last_run_at = None
        except Exception:
            last_status = "Unknown"
            last_run_at = None

        result.append(
            {
                "job_id": job_id,
                "name": job_name,
                "last_status": last_status,
                "last_run_at": last_run_at,
            }
        )

    return result


def trigger_scraper_job(job_id: int) -> dict:
    wc = get_workspace_client()
    run = wc.jobs.run_now(job_id=job_id)
    run_url = f"{wc.config.host}/jobs/{job_id}/runs/{run.run_id}"
    return {"run_id": run.run_id, "run_url": run_url}
