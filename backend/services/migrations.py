import logging

from backend.config import PIPELINE_RUNS_TABLE
from backend.services.databricks_client import run_statement

logger = logging.getLogger(__name__)

_MIGRATIONS = [
    (
        "add error_log to pipeline_runs",
        f"ALTER TABLE {PIPELINE_RUNS_TABLE} ADD COLUMN error_log STRING COMMENT 'Error message or traceback if status=failed'",
    ),
]


def run_migrations() -> None:
    for name, sql in _MIGRATIONS:
        try:
            run_statement(sql)
            logger.info("Migration OK: %s", name)
        except Exception as e:
            msg = str(e)
            # Delta raises an error if the column already exists — that's fine
            if "already exists" in msg.lower() or "duplicate" in msg.lower():
                logger.debug("Migration skipped (already applied): %s", name)
            else:
                logger.warning("Migration failed: %s — %s", name, msg)

    # OPTIMIZE rewrites Delta files and refreshes statistics, fixing inconsistencies
    # between COUNT(*) (which uses cached stats) and SELECT (which reads actual files).
    try:
        run_statement(f"OPTIMIZE {PIPELINE_RUNS_TABLE}")
        logger.info("OPTIMIZE pipeline_runs OK")
    except Exception as e:
        logger.warning("OPTIMIZE pipeline_runs failed: %s", e)
