from pydantic import BaseModel


class ColumnMapping(BaseModel):
    url: str | None = None
    team: str | None = None
    abuse_area: str | None = None
    sub_abuse_area: str | None = None
    notes: str | None = None
    relevancy: str | None = None


class ImportRequest(BaseModel):
    mapping: ColumnMapping
    platform_override: str = "Auto-detect from URL"
    col_hint_platform: str | None = None
    manual_values: dict[str, str] = {}
    meta_mapping: dict[str, str] = {}
    row_filters: dict[str, list[str]] = {}


class ImportResult(BaseModel):
    imported: int
    skipped: int
    errors: list[str]
    batches: int
