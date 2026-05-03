"""
Databricks Job task — deduplicates social_sources_staging into social_sources.

Run as a Python task in a Databricks Job.
"""

import os

from databricks import sql

host = os.environ["DATABRICKS_HOST"].rstrip("/").replace("https://", "")
token = os.environ["DATABRICKS_TOKEN"]
warehouse_id = os.environ["DATABRICKS_WAREHOUSE_ID"]
http_path = f"/sql/1.0/warehouses/{warehouse_id}"

SOURCES_TABLE = "af_delivery_dev.data_collection.social_sources"
STAGING_TABLE = "af_delivery_dev.data_collection.social_sources_staging"

conn_params = dict(server_hostname=host, http_path=http_path, access_token=token)


def run(query: str):
    with sql.connect(**conn_params) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            if cursor.description:
                return cursor.fetchall()
    return []


rows_before = run(f"SELECT COUNT(*) AS n FROM {STAGING_TABLE}")[0][0]
print(f"Staging rows before dedup: {rows_before}")

run(f"""
    MERGE INTO {SOURCES_TABLE} AS t
    USING (
        SELECT
            uuid()                                  AS id,
            url,
            platform,
            team,
            abuse_area,
            sub_abuse_area,
            notes,
            relevancy,
            COALESCE(metadata, '{{}}')              AS metadata,
            COALESCE(added_at, current_timestamp()) AS added_at,
            COALESCE(added_by, 'scraper')           AS added_by
        FROM {STAGING_TABLE}
    ) AS s
    ON t.url = s.url
    WHEN NOT MATCHED THEN
        INSERT (id, url, platform, team, abuse_area, sub_abuse_area,
                notes, relevancy, metadata, added_at, added_by)
        VALUES (s.id, s.url, s.platform, s.team, s.abuse_area, s.sub_abuse_area,
                s.notes, s.relevancy, s.metadata, s.added_at, s.added_by)
""")

run(f"DELETE FROM {STAGING_TABLE}")

rows_after = run(f"SELECT COUNT(*) AS n FROM {STAGING_TABLE}")[0][0]
print(f"Staging rows remaining: {rows_after}")
print("Deduplication complete.")
