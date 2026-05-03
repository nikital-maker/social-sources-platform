"""
Run once to create (or recreate) the Unity Catalog schema and Delta tables.

Usage:
    python setup_tables.py
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

STATEMENTS = [
    "DROP TABLE IF EXISTS af_delivery_dev.data_collection.social_sources_staging",
    "DROP TABLE IF EXISTS af_delivery_dev.data_collection.social_sources",
    """
    CREATE TABLE IF NOT EXISTS af_delivery_dev.data_collection.social_sources (
        id             STRING    NOT NULL COMMENT 'UUID primary key',
        url            STRING    NOT NULL COMMENT 'Source URL or account link',
        platform       STRING    COMMENT 'Telegram | Twitter/X | TikTok | Instagram | YouTube | Facebook | Other',
        team           STRING    COMMENT 'Owning team: CT, HS, CS, etc.',
        abuse_area     STRING    COMMENT 'Comma-separated abuse area classifications',
        sub_abuse_area STRING    COMMENT 'Comma-separated sub-classifications',
        notes          STRING,
        relevancy      STRING    COMMENT 'Yes | No | Low | Medium | High | True | False',
        metadata       STRING    COMMENT 'JSON: name, username, bio, profile_pic',
        added_at       TIMESTAMP NOT NULL,
        added_by       STRING
    )
    USING DELTA
    COMMENT 'Master social media sources'
    """,
    """
    CREATE TABLE IF NOT EXISTS af_delivery_dev.data_collection.social_sources_staging (
        id             STRING,
        url            STRING    NOT NULL,
        platform       STRING,
        team           STRING,
        abuse_area     STRING,
        sub_abuse_area STRING,
        notes          STRING,
        relevancy      STRING,
        metadata       STRING,
        added_at       TIMESTAMP,
        added_by       STRING,
        scraper_name   STRING    COMMENT 'Name of the scraper job that wrote this row',
        raw_record     STRING    COMMENT 'Original JSON payload from the scraper'
    )
    USING DELTA
    COMMENT 'Raw staging feed from scraper jobs, pending review/dedup'
    """,
]

with sql.connect(server_hostname=host, http_path=http_path, access_token=token) as conn:
    with conn.cursor() as cursor:
        for stmt in STATEMENTS:
            cursor.execute(stmt)

print("Tables created:")
print("  af_delivery_dev.data_collection.social_sources")
print("  af_delivery_dev.data_collection.social_sources_staging")
