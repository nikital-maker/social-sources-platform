"""
Run once to create (or recreate) the Unity Catalog schema and Delta tables.

Usage:
    python setup_tables.py

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

TEAM_TABLES = {
    "Child Safety":       "social_sources_child_safety",
    "Human Exploitation": "social_sources_human_exploitation",
    "Hate Speech":        "social_sources_hate_speech",
    "NCII":               "social_sources_ncii",
    "Illegal Goods":      "social_sources_illegal_goods",
}

_SOURCES_DDL = """
    CREATE TABLE IF NOT EXISTS {table} (
        id             STRING    NOT NULL COMMENT 'UUID primary key',
        url            STRING    NOT NULL COMMENT 'Source URL or account link',
        platform       STRING    COMMENT 'Telegram | Twitter/X | TikTok | Instagram | YouTube | Facebook | Other',
        team           STRING    COMMENT 'Team name matching the table',
        abuse_area     STRING    COMMENT 'Comma-separated abuse area classifications',
        sub_abuse_area STRING    COMMENT 'Comma-separated sub-classifications',
        notes          STRING,
        relevancy      STRING    COMMENT 'Yes | No | Low | Medium | High | True | False',
        metadata       STRING    COMMENT 'JSON: name, username, bio, profile_pic',
        added_at       TIMESTAMP NOT NULL,
        added_by       STRING
    )
    USING DELTA
    COMMENT '{team} social media sources'
"""

_STAGING_DDL = f"""
    CREATE TABLE IF NOT EXISTS {_SCHEMA}.social_sources_staging (
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
"""

STATEMENTS = [f"DROP TABLE IF EXISTS {_SCHEMA}.social_sources"]

# Drop and recreate team tables
for team, table_name in TEAM_TABLES.items():
    full_table = f"{_SCHEMA}.{table_name}"
    STATEMENTS.append(f"DROP TABLE IF EXISTS {full_table}")
    STATEMENTS.append(_SOURCES_DDL.format(table=full_table, team=team))

# Staging table
STATEMENTS.append(f"DROP TABLE IF EXISTS {_SCHEMA}.social_sources_staging")
STATEMENTS.append(_STAGING_DDL)

with sql.connect(server_hostname=host, http_path=http_path, access_token=token) as conn:
    with conn.cursor() as cursor:
        for stmt in STATEMENTS:
            cursor.execute(stmt)

print("Tables created:")
for team, table_name in TEAM_TABLES.items():
    print(f"  {_SCHEMA}.{table_name}  ({team})")
print(f"  {_SCHEMA}.social_sources_staging")
