from datetime import datetime

from pydantic import BaseModel


class Source(BaseModel):
    id: str
    url: str
    platform: str | None = None
    team: str | None = None
    abuse_area: str | None = None
    sub_abuse_area: str | None = None
    notes: str | None = None
    relevancy: str | None = None
    metadata: str | None = None
    added_at: str | None = None
    added_by: str | None = None


class SourceCreate(BaseModel):
    url: str
    platform: str | None = None
    abuse_area: str = ""
    sub_abuse_area: str = ""
    notes: str = ""
    relevancy: str = ""
    auto_detect_platform: bool = True


class SourcesPage(BaseModel):
    items: list[Source]
    total: int


class DeleteRequest(BaseModel):
    ids: list[str]


class DailyCount(BaseModel):
    date: str
    count: int


class DashboardData(BaseModel):
    total_sources: int
    added_this_week: int
    platforms_count: int
    by_platform: dict[str, int]
    by_relevancy: dict[str, int]
    daily_counts: list[DailyCount]
