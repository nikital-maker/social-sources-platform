"""
Run once to create the Unity Catalog schema and Delta tables.

Usage:
    python setup_tables.py
"""

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from databricks.connect import DatabricksSession

spark = DatabricksSession.builder.getOrCreate()

# Create catalog schema if missing
spark.sql("CREATE SCHEMA IF NOT EXISTS main.social")

# ---------------------------------------------------------------------------
# sources — master deduplicated table
# ---------------------------------------------------------------------------
spark.sql(
    """
    CREATE TABLE IF NOT EXISTS main.social.sources (
        id           STRING    NOT NULL COMMENT 'UUID primary key',
        platform     STRING    NOT NULL COMMENT 'Telegram | Twitter | TikTok',
        identifier   STRING    NOT NULL COMMENT '@handle, channel URL, etc.',
        display_name STRING,
        metadata     STRING    COMMENT 'JSON blob for extra attributes',
        status       STRING    NOT NULL COMMENT 'active | inactive',
        added_at     TIMESTAMP NOT NULL,
        last_seen_at TIMESTAMP NOT NULL,
        added_by     STRING
    )
    USING DELTA
    COMMENT 'Master deduplicated social media sources'
    """
)

# Delta Lake does not enforce UNIQUE constraints but we record the intent
# via a table property for documentation and upstream tooling.
spark.sql(
    """
    ALTER TABLE main.social.sources
    SET TBLPROPERTIES ('unique_key' = 'platform,identifier')
    """
)

# ---------------------------------------------------------------------------
# sources_staging — raw feed from scrapers
# ---------------------------------------------------------------------------
spark.sql(
    """
    CREATE TABLE IF NOT EXISTS main.social.sources_staging (
        id           STRING,
        platform     STRING    NOT NULL,
        identifier   STRING    NOT NULL,
        display_name STRING,
        metadata     STRING,
        status       STRING,
        added_at     TIMESTAMP,
        last_seen_at TIMESTAMP,
        added_by     STRING,
        scraper_name STRING    COMMENT 'Name of the scraper job that wrote this row',
        raw_record   STRING    COMMENT 'Original JSON payload from the scraper'
    )
    USING DELTA
    COMMENT 'Raw staging feed from scraper jobs, pending review/dedup'
    """
)

print("Tables created (or already exist):")
print("  main.social.sources")
print("  main.social.sources_staging")
