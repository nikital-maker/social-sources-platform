from pydantic import BaseModel


class SyncConfigCreate(BaseModel):
    spreadsheet_id: str
    spreadsheet_url: str
    spreadsheet_name: str
    tab_title: str
    gid: int
    team: str
    mapping_json: str = "{}"
    platform_override: str = "Auto-detect from URL"
    manual_values_json: str = "{}"
    meta_mapping_json: str = "{}"
    sync_interval_minutes: int = 30


class SyncConfigUpdate(BaseModel):
    sync_enabled: bool | None = None
    sync_interval_minutes: int | None = None
    mapping_json: str | None = None
    platform_override: str | None = None
    manual_values_json: str | None = None
    meta_mapping_json: str | None = None


class SyncConfig(BaseModel):
    id: str
    spreadsheet_id: str
    spreadsheet_url: str
    spreadsheet_name: str
    tab_title: str
    gid: int
    team: str
    mapping_json: str
    platform_override: str
    manual_values_json: str
    meta_mapping_json: str
    sync_enabled: bool
    sync_interval_minutes: int
    last_sync_at: str | None = None
    last_sync_rows: int | None = None
    last_sync_error: str | None = None
    created_at: str | None = None
    created_by: str | None = None


class SyncResult(BaseModel):
    config_id: str
    imported: int
    skipped: int
    errors: list[str]
