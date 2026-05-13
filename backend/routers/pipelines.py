from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_current_user, validate_team
from backend.models.pipeline import (
    GoogleDorkingResult,
    PipelineResultsPage,
    PipelineRun,
    PipelineRunCreate,
    PipelineRunsPage,
)
from backend.services.pipeline import (
    create_pipeline_run,
    delete_pipeline_run,
    fail_pipeline_run,
    get_google_dorking_results,
    get_pipeline_run,
    get_pipeline_runs,
    get_recent_pipeline_errors,
    trigger_google_dorking_job,
)

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@router.get("", response_model=PipelineRunsPage)
async def list_pipeline_runs(
    team: str,
    page: int = 1,
    page_size: int = 20,
    _team: str = Depends(validate_team),
):
    return get_pipeline_runs(team=team, page=page, page_size=page_size)


@router.post("", response_model=PipelineRun, status_code=201)
async def start_pipeline(
    body: PipelineRunCreate,
    current_user: str = Depends(get_current_user),
):
    validate_team(body.team)

    run = create_pipeline_run(
        team=body.team,
        pipeline_type=body.pipeline_type,
        config=body.config,
        created_by=current_user,
    )

    try:
        databricks_run_id = trigger_google_dorking_job(
            run_id=run.id,
            team=body.team,
            config=body.config,
        )
        run.databricks_run_id = databricks_run_id
        run.status = "running"
    except Exception as e:
        error_msg = str(e)
        try:
            fail_pipeline_run(run.id, error_msg)
        except Exception:
            pass
        run.status = "failed"
        run.error_log = error_msg

    return run


@router.get("/errors", response_model=list[PipelineRun])
async def list_pipeline_errors(limit: int = 20):
    return get_recent_pipeline_errors(limit=limit)


@router.get("/{run_id}", response_model=PipelineRun)
async def get_run(run_id: str):
    run = get_pipeline_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return run


@router.delete("/{run_id}", status_code=204)
async def delete_run(run_id: str):
    run = get_pipeline_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    delete_pipeline_run(run_id)


@router.get("/{run_id}/results", response_model=PipelineResultsPage)
async def get_results(run_id: str, page: int = 1, page_size: int = 50):
    run = get_pipeline_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return get_google_dorking_results(run_id=run_id, page=page, page_size=page_size)
