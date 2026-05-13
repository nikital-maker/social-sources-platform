import logging
import os

import pandas as pd
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition

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
            disposition=Disposition.INLINE,
        )
        _check_statement_response(response)
        if response.result is None or response.manifest is None:
            return pd.DataFrame()
        cols = [col.name for col in (response.manifest.schema.columns or [])]
        log.info("run_query manifest: total_row_count=%s truncated=%s", response.manifest.total_row_count, response.manifest.truncated)

        all_rows: list = list(response.result.data_array or [])

        # Fetch remaining chunks if result is paginated
        statement_id = response.statement_id
        next_chunk = response.result.next_chunk_index
        while next_chunk is not None:
            chunk = wc.statement_execution.get_statement_result_chunk_n(
                statement_id=statement_id, chunk_index=next_chunk
            )
            all_rows.extend(chunk.data_array or [])
            next_chunk = chunk.next_chunk_index

        log.info("run_query: returned %d rows", len(all_rows))
        return pd.DataFrame(all_rows, columns=cols)
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
