import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from backend.config import WORKFLOW_CONFIG
from backend.models.job import JobDetail, RunStatus, TaskStatus, WorkflowConfig
from backend.services.job_monitor import cancel_run, get_job_details, get_run_status, trigger_job

router = APIRouter(prefix="/jobs", tags=["jobs"])

_POLL_INTERVAL_S = 15


@router.get("/workflow-config")
async def get_workflow_config(team: str) -> WorkflowConfig | None:
    cfg = WORKFLOW_CONFIG.get(team)
    if not cfg:
        return None
    return WorkflowConfig(team=team, **cfg)


@router.get("/{job_id}/details", response_model=JobDetail)
async def job_details(job_id: int):
    try:
        return get_job_details(job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{job_id}/run")
async def run_job(job_id: int):
    try:
        return trigger_job(job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/runs/{run_id}/cancel")
async def cancel_job_run(run_id: int):
    try:
        cancel_run(run_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}


@router.get("/runs/{run_id}/status", response_model=RunStatus)
async def run_status(run_id: int):
    try:
        data = get_run_status(run_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return RunStatus(
        **{k: v for k, v in data.items() if k != "tasks"},
        tasks=[TaskStatus(**t) for t in data["tasks"]],
    )


@router.get("/runs/{run_id}/stream")
async def stream_run_status(run_id: int):
    start = datetime.now()

    async def event_generator():
        while True:
            try:
                data = get_run_status(run_id)
            except Exception as e:
                yield {"event": "error", "data": json.dumps({"detail": str(e)})}
                return

            elapsed = int((datetime.now() - start).total_seconds())
            status = RunStatus(
                **{k: v for k, v in data.items() if k != "tasks"},
                elapsed_seconds=elapsed,
                tasks=[TaskStatus(**t) for t in data["tasks"]],
            )
            payload = status.model_dump_json()

            if data["is_done"]:
                yield {"event": "done", "data": payload}
                return
            else:
                yield {"event": "status", "data": payload}

            await asyncio.sleep(_POLL_INTERVAL_S)

    return EventSourceResponse(event_generator())
