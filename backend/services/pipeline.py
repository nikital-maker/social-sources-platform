import json
import uuid
from datetime import datetime, timezone

from databricks.sdk import WorkspaceClient

from backend.config import (
    GOOGLE_DORKING_JOB_ID,
    PIPELINE_RESULTS_GOOGLE_DORKING_TABLE,
    PIPELINE_RUNS_TABLE,
    TABLE_SUFFIX as _TABLE_SUFFIX,
)
from backend.models.pipeline import (
    GoogleDorkingConfig,
    GoogleDorkingResult,
    PipelineRun,
    PipelineResultsPage,
    PipelineRunsPage,
)
from backend.services.databricks_client import run_query, run_statement


def create_pipeline_run(team: str, pipeline_type: str, config: GoogleDorkingConfig, created_by: str) -> PipelineRun:
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    config_json = config.model_dump_json()

    run_statement(f"""
        INSERT INTO {PIPELINE_RUNS_TABLE}
        (id, team, pipeline_type, config_json, status, created_at, created_by)
        VALUES (
            '{run_id}',
            '{team.replace("'", "\\'")}',
            '{pipeline_type}',
            '{config_json.replace("'", "\\'")}',
            'pending',
            '{now}',
            '{created_by.replace("'", "\\'")}'
        )
    """)

    return PipelineRun(
        id=run_id,
        team=team,
        pipeline_type=pipeline_type,
        config_json=config_json,
        status="pending",
        created_at=datetime.fromisoformat(now),
        created_by=created_by,
    )


def trigger_google_dorking_job(run_id: str, team: str, config: GoogleDorkingConfig) -> int:
    w = WorkspaceClient()

    notebook_params = {
        "keywords": ",".join(config.keywords),
        "sites": ",".join(config.sites),
        "clients": ",".join(config.clients),
        "rule_out": ",".join(config.rule_out),
        "timeframe": str(config.timeframe),
        "num_of_results": str(config.num_of_results),
        "verbatim": "true" if config.verbatim else "false",
        "team": team,
        "pipeline_run_id": run_id,
        "table_suffix": _TABLE_SUFFIX,
    }

    response = w.jobs.run_now(job_id=GOOGLE_DORKING_JOB_ID, notebook_params=notebook_params)
    databricks_run_id = response.run_id

    run_statement(f"""
        UPDATE {PIPELINE_RUNS_TABLE}
        SET status = 'running', databricks_run_id = {databricks_run_id}
        WHERE id = '{run_id}'
    """)

    return databricks_run_id


def fail_pipeline_run(run_id: str, error: str) -> None:
    error_escaped = error.replace("'", "\\'")
    run_statement(f"""
        UPDATE {PIPELINE_RUNS_TABLE}
        SET status = 'failed', error_log = '{error_escaped}', completed_at = current_timestamp()
        WHERE id = '{run_id.replace("'", "\\'")}'
    """)


def get_pipeline_runs(team: str, page: int = 1, page_size: int = 20) -> PipelineRunsPage:
    offset = (page - 1) * page_size
    team_escaped = team.replace("'", "\\'")

    count_df = run_query(f"SELECT COUNT(*) as total FROM {PIPELINE_RUNS_TABLE} WHERE team = '{team_escaped}'")
    df = run_query(f"""
        SELECT id, team, pipeline_type, config_json, status,
               databricks_run_id, row_count, error_log, created_at, created_by, completed_at
        FROM {PIPELINE_RUNS_TABLE}
        WHERE team = '{team_escaped}'
    """)

    total = len(df)
    df = df.sort_values("created_at", ascending=False).iloc[offset: offset + page_size]

    items = [
        PipelineRun(
            id=row["id"],
            team=row["team"],
            pipeline_type=row["pipeline_type"],
            config_json=row["config_json"] or "{}",
            status=row["status"],
            databricks_run_id=row.get("databricks_run_id"),
            row_count=row.get("row_count"),
            created_at=row["created_at"],
            created_by=row.get("created_by"),
            completed_at=row.get("completed_at"),
        )
        for _, row in df.iterrows()
    ]

    return PipelineRunsPage(items=items, total=total)


def get_pipeline_run(run_id: str) -> PipelineRun | None:
    df = run_query(f"""
        SELECT id, team, pipeline_type, config_json, status,
               databricks_run_id, row_count, error_log, created_at, created_by, completed_at
        FROM {PIPELINE_RUNS_TABLE}
        WHERE id = '{run_id.replace("'", "\\'")}'
    """)
    if df.empty:
        return None
    row = df.iloc[0]
    return PipelineRun(
        id=row["id"],
        team=row["team"],
        pipeline_type=row["pipeline_type"],
        config_json=row["config_json"] or "{}",
        status=row["status"],
        databricks_run_id=row.get("databricks_run_id"),
        row_count=row.get("row_count"),
        error_log=row.get("error_log"),
        created_at=row["created_at"],
        created_by=row.get("created_by"),
        completed_at=row.get("completed_at"),
    )


def delete_pipeline_run(run_id: str) -> None:
    eid = run_id.replace("'", "\\'")
    run_statement(f"DELETE FROM {PIPELINE_RESULTS_GOOGLE_DORKING_TABLE} WHERE pipeline_run_id = '{eid}'")
    run_statement(f"DELETE FROM {PIPELINE_RUNS_TABLE} WHERE id = '{eid}'")


def get_recent_pipeline_errors(limit: int = 20) -> list[PipelineRun]:
    df = run_query(f"""
        SELECT id, team, pipeline_type, config_json, status,
               databricks_run_id, row_count, error_log, created_at, created_by, completed_at
        FROM {PIPELINE_RUNS_TABLE}
        WHERE status = 'failed'
    """)
    return [
        PipelineRun(
            id=row["id"],
            team=row["team"],
            pipeline_type=row["pipeline_type"],
            config_json=row["config_json"] or "{}",
            status=row["status"],
            databricks_run_id=row.get("databricks_run_id"),
            row_count=row.get("row_count"),
            error_log=row.get("error_log"),
            created_at=row["created_at"],
            created_by=row.get("created_by"),
            completed_at=row.get("completed_at"),
        )
        for _, row in df.iterrows()
    ]


def get_google_dorking_results(run_id: str, page: int = 1, page_size: int = 50) -> PipelineResultsPage:
    offset = (page - 1) * page_size
    run_id_escaped = run_id.replace("'", "\\'")

    df = run_query(f"""
        SELECT id, pipeline_run_id, team, query, href, title, body, created_at
        FROM {PIPELINE_RESULTS_GOOGLE_DORKING_TABLE}
        WHERE pipeline_run_id = '{run_id_escaped}'
    """)

    total = len(df)
    df = df.sort_values("created_at", ascending=True).iloc[offset: offset + page_size]

    items = [
        GoogleDorkingResult(
            id=row["id"],
            pipeline_run_id=row["pipeline_run_id"],
            team=row["team"],
            query=row.get("query"),
            href=row.get("href"),
            title=row.get("title"),
            body=row.get("body"),
            created_at=row["created_at"],
        )
        for _, row in df.iterrows()
    ]

    return PipelineResultsPage(items=items, total=total, page=page, page_size=page_size)
