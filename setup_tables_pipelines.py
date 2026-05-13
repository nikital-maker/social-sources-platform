"""
Run once to create (or recreate) pipeline Delta tables.
Drops and recreates: pipeline_runs, pipeline_results_google_dorking.

WARNING: Drops existing tables first — do not run against production data.
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from databricks import sql

host = os.environ["DATABRICKS_HOST"].rstrip("/").replace("https://", "")
token = os.environ["DATABRICKS_TOKEN"]
warehouse_id = os.environ["DATABRICKS_WAREHOUSE_ID"]
http_path = f"/sql/1.0/warehouses/{warehouse_id}"

_SCHEMA = "af_delivery_dev.data_collection"
_TABLE_SUFFIX = os.environ.get("TABLE_SUFFIX", "")

_PIPELINE_RUNS_DDL = f"""
    CREATE TABLE IF NOT EXISTS {_SCHEMA}.pipeline_runs{_TABLE_SUFFIX} (
        id                  STRING    NOT NULL COMMENT 'UUID primary key',
        team                STRING    NOT NULL COMMENT 'Team name',
        pipeline_type       STRING    NOT NULL COMMENT 'e.g. google_dorking',
        config_json         STRING    COMMENT 'JSON snapshot of input parameters',
        status              STRING    NOT NULL COMMENT 'pending | running | completed | failed',
        databricks_run_id   BIGINT    COMMENT 'Databricks job run ID',
        row_count           INT       COMMENT 'Number of results written',
        error_log           STRING    COMMENT 'Error message or traceback if status=failed',
        created_at          TIMESTAMP NOT NULL,
        created_by          STRING,
        completed_at        TIMESTAMP
    )
    USING DELTA
    COMMENT 'Pipeline execution history'
"""

_PIPELINE_RESULTS_GOOGLE_DORKING_DDL = f"""
    CREATE TABLE IF NOT EXISTS {_SCHEMA}.pipeline_results_google_dorking{_TABLE_SUFFIX} (
        id                  STRING    NOT NULL COMMENT 'UUID primary key',
        pipeline_run_id     STRING    NOT NULL COMMENT 'FK to pipeline_runs.id',
        team                STRING    NOT NULL,
        query               STRING    COMMENT 'The formatted query that returned this result',
        href                STRING    COMMENT 'Result URL',
        title               STRING    COMMENT 'Page title',
        body                STRING    COMMENT 'Result snippet / body text',
        created_at          TIMESTAMP NOT NULL
    )
    USING DELTA
    COMMENT 'Google Dorking pipeline results'
"""

pipeline_runs_table = f"{_SCHEMA}.pipeline_runs{_TABLE_SUFFIX}"
pipeline_results_gd_table = f"{_SCHEMA}.pipeline_results_google_dorking{_TABLE_SUFFIX}"

STATEMENTS = [
    f"DROP TABLE IF EXISTS {pipeline_runs_table}",
    _PIPELINE_RUNS_DDL,
    f"DROP TABLE IF EXISTS {pipeline_results_gd_table}",
    _PIPELINE_RESULTS_GOOGLE_DORKING_DDL,
]

with sql.connect(server_hostname=host, http_path=http_path, access_token=token) as conn:
    with conn.cursor() as cursor:
        for stmt in STATEMENTS:
            cursor.execute(stmt)

suffix_note = f" (suffix: {_TABLE_SUFFIX!r})" if _TABLE_SUFFIX else ""
print(f"Pipeline tables created{suffix_note}:")
print(f"  {pipeline_runs_table}")
print(f"  {pipeline_results_gd_table}")
