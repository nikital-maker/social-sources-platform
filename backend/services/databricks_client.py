import logging
import os

import pandas as pd
from databricks.sdk import WorkspaceClient

log = logging.getLogger(__name__)

_workspace_client: WorkspaceClient | None = None


def get_workspace_client() -> WorkspaceClient:
    global _workspace_client
    if _workspace_client is None:
        _workspace_client = WorkspaceClient()
    return _workspace_client


def _check_statement_response(response) -> None:
    if response.status and response.status.error:
        raise Exception(response.status.error.message)


def run_query(query: str) -> pd.DataFrame:
    log.info("run_query: %s", query[:120].strip())
    try:
        wc = get_workspace_client()
        warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
        response = wc.statement_execution.execute_statement(
            statement=query,
            warehouse_id=warehouse_id,
            wait_timeout="50s",
        )
        _check_statement_response(response)
        if response.result is None or response.manifest is None:
            return pd.DataFrame()
        cols = [col.name for col in (response.manifest.schema.columns or [])]
        data = response.result.data_array or []
        log.info("run_query: returned %d rows", len(data))
        return pd.DataFrame(data, columns=cols)
    except Exception:
        log.exception("run_query failed")
        raise


def run_statement(statement: str) -> None:
    log.info("run_statement: %s", statement[:120].strip())
    try:
        wc = get_workspace_client()
        warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
        response = wc.statement_execution.execute_statement(
            statement=statement,
            warehouse_id=warehouse_id,
            wait_timeout="50s",
        )
        _check_statement_response(response)
        log.info("run_statement: OK")
    except Exception:
        log.exception("run_statement failed")
        raise


def current_user() -> str:
    try:
        me = get_workspace_client().current_user.me()
        if me.user_name and "@" in me.user_name:
            return me.user_name
        if me.display_name:
            return me.display_name
        return me.user_name or "unknown"
    except Exception:
        return "local_dev"
