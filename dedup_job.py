"""
Databricks Job task — deduplicates sources_staging into sources.

Run as a Python task in a Databricks Job (DatabricksSession auto-connects).
"""

from databricks.connect import DatabricksSession

spark = DatabricksSession.builder.getOrCreate()

staging_count_before = spark.table("main.social.sources_staging").count()
print(f"Staging rows before dedup: {staging_count_before}")

# MERGE staging → sources
merge_result = spark.sql(
    """
    MERGE INTO main.social.sources AS t
    USING (
        SELECT
            uuid()                      AS id,
            platform,
            identifier,
            display_name,
            metadata,
            COALESCE(status, 'active')  AS status,
            COALESCE(added_at, current_timestamp())     AS added_at,
            current_timestamp()         AS last_seen_at,
            COALESCE(added_by, 'scraper') AS added_by
        FROM main.social.sources_staging
    ) AS s
    ON t.platform = s.platform AND t.identifier = s.identifier
    WHEN MATCHED THEN
        UPDATE SET t.last_seen_at = current_timestamp()
    WHEN NOT MATCHED THEN
        INSERT (id, platform, identifier, display_name, metadata, status,
                added_at, last_seen_at, added_by)
        VALUES (s.id, s.platform, s.identifier, s.display_name, s.metadata,
                s.status, s.added_at, s.last_seen_at, s.added_by)
    """
)

# Collect merge metrics from the operation history
history = spark.sql(
    "DESCRIBE HISTORY main.social.sources LIMIT 1"
).collect()
if history:
    op_metrics = history[0]["operationMetrics"] or {}
    rows_inserted = op_metrics.get("numTargetRowsInserted", "?")
    rows_updated = op_metrics.get("numTargetRowsUpdated", "?")
    print(f"Rows inserted: {rows_inserted}")
    print(f"Rows updated:  {rows_updated}")

# Delete merged rows from staging
spark.sql("DELETE FROM main.social.sources_staging")

staging_count_after = spark.table("main.social.sources_staging").count()
print(f"Staging rows remaining: {staging_count_after}")
print("Deduplication complete.")
