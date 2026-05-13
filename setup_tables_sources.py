"""
Run once to create (or recreate) social sources Delta tables.
Drops and recreates: per-team source tables, staging, gsheet_sync_config.

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

TEAM_TABLES = {
    "Child Safety":       f"social_sources_child_safety{_TABLE_SUFFIX}",
    "Human Exploitation": f"social_sources_human_exploitation{_TABLE_SUFFIX}",
    "Hate Speech":        f"social_sources_hate_speech{_TABLE_SUFFIX}",
    "NCII":               f"social_sources_ncii{_TABLE_SUFFIX}",
    "Illegal Goods":      f"social_sources_illegal_goods{_TABLE_SUFFIX}",
    "TEST":               f"social_sources_test{_TABLE_SUFFIX}",
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
    CREATE TABLE IF NOT EXISTS {_SCHEMA}.social_sources_staging{_TABLE_SUFFIX} (
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

_SYNC_CONFIG_DDL = f"""
    CREATE TABLE IF NOT EXISTS {_SCHEMA}.gsheet_sync_config{_TABLE_SUFFIX} (
        id                    STRING    NOT NULL COMMENT 'UUID primary key',
        spreadsheet_id        STRING    NOT NULL COMMENT 'Google Sheets spreadsheet ID',
        spreadsheet_url       STRING    NOT NULL COMMENT 'Full Google Sheets URL',
        spreadsheet_name      STRING    NOT NULL COMMENT 'Human-readable sheet name',
        tab_title             STRING    NOT NULL COMMENT 'Worksheet tab name',
        gid                   INT       NOT NULL COMMENT 'Worksheet GID',
        team                  STRING    NOT NULL COMMENT 'Target team name',
        mapping_json          STRING    COMMENT 'JSON column mapping config',
        platform_override     STRING    COMMENT 'Platform override or Auto-detect from URL',
        manual_values_json    STRING    COMMENT 'JSON manual value overrides',
        meta_mapping_json     STRING    COMMENT 'JSON metadata column mapping',
        sync_enabled          BOOLEAN,
        sync_interval_minutes INT,
        last_sync_at          TIMESTAMP,
        last_sync_rows        INT,
        last_sync_error       STRING,
        created_at            TIMESTAMP NOT NULL,
        created_by            STRING
    )
    USING DELTA
    COMMENT 'Google Sheets auto-sync configuration'
"""

STATEMENTS = []

for team, table_name in TEAM_TABLES.items():
    full_table = f"{_SCHEMA}.{table_name}"
    STATEMENTS.append(f"DROP TABLE IF EXISTS {full_table}")
    STATEMENTS.append(_SOURCES_DDL.format(table=full_table, team=team))

staging_table = f"{_SCHEMA}.social_sources_staging{_TABLE_SUFFIX}"
STATEMENTS.append(f"DROP TABLE IF EXISTS {staging_table}")
STATEMENTS.append(_STAGING_DDL)

sync_config_table = f"{_SCHEMA}.gsheet_sync_config{_TABLE_SUFFIX}"
STATEMENTS.append(f"DROP TABLE IF EXISTS {sync_config_table}")
STATEMENTS.append(_SYNC_CONFIG_DDL)

with sql.connect(server_hostname=host, http_path=http_path, access_token=token) as conn:
    with conn.cursor() as cursor:
        for stmt in STATEMENTS:
            cursor.execute(stmt)

suffix_note = f" (suffix: {_TABLE_SUFFIX!r})" if _TABLE_SUFFIX else ""
print(f"Sources tables created{suffix_note}:")
for team, table_name in TEAM_TABLES.items():
    print(f"  {_SCHEMA}.{table_name}  ({team})")
print(f"  {staging_table}")
print(f"  {sync_config_table}")
