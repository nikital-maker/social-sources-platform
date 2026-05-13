from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GoogleDorkingConfig(BaseModel):
    keywords: list[str] = Field(min_length=1)
    sites: list[str] = []
    clients: list[str] = []
    rule_out: list[str] = []
    timeframe: Literal[7, 30, 90, 365] = 30
    num_of_results: int = 100
    verbatim: bool = True


class PipelineRunCreate(BaseModel):
    team: str
    pipeline_type: Literal["google_dorking"]
    config: GoogleDorkingConfig


class PipelineRun(BaseModel):
    id: str
    team: str
    pipeline_type: str
    config_json: str
    status: str
    databricks_run_id: int | None = None
    row_count: int | None = None
    error_log: str | None = None
    created_at: datetime
    created_by: str | None = None
    completed_at: datetime | None = None


class PipelineRunsPage(BaseModel):
    items: list[PipelineRun]
    total: int


class GoogleDorkingResult(BaseModel):
    id: str
    pipeline_run_id: str
    team: str
    query: str | None = None
    href: str | None = None
    title: str | None = None
    body: str | None = None
    created_at: datetime


class PipelineResultsPage(BaseModel):
    items: list[GoogleDorkingResult]
    total: int
    page: int
    page_size: int
