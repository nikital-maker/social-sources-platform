import uuid

import pandas as pd

from backend.config import STAGING_TABLE
from backend.services.databricks_client import current_user, run_query, run_statement


def load_staging(sources_table: str) -> pd.DataFrame:
    return run_query(f"""
        SELECT s.*
        FROM {STAGING_TABLE} s
        LEFT ANTI JOIN {sources_table} m ON s.url = m.url
    """)


def approve_staged(row: dict, target_table: str, user: str | None = None) -> None:
    if user is None:
        user = current_user()

    url = str(row.get("url", "")).replace("'", "\\'")
    new_id = str(uuid.uuid4())
    user_esc = user.replace("'", "\\'")

    def sr(field: str) -> str:
        return str(row.get(field, "") or "").replace("'", "\\'")

    run_statement(f"""
        MERGE INTO {target_table} AS t
        USING (SELECT
            '{new_id}'               AS id,
            '{url}'                  AS url,
            '{sr("platform")}'       AS platform,
            '{sr("team")}'           AS team,
            '{sr("abuse_area")}'     AS abuse_area,
            '{sr("sub_abuse_area")}' AS sub_abuse_area,
            '{sr("notes")}'          AS notes,
            '{sr("relevancy")}'      AS relevancy,
            '{sr("metadata")}'       AS metadata,
            current_timestamp()      AS added_at,
            '{user_esc}'             AS added_by
        ) AS src
        ON t.url = src.url
        WHEN MATCHED THEN UPDATE SET t.added_at = current_timestamp()
        WHEN NOT MATCHED THEN INSERT *
    """)
    run_statement(f"DELETE FROM {STAGING_TABLE} WHERE url = '{url}'")


def reject_staged(url: str) -> None:
    url_esc = str(url).replace("'", "\\'")
    run_statement(f"DELETE FROM {STAGING_TABLE} WHERE url = '{url_esc}'")
