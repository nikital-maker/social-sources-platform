from pydantic import BaseModel


class TaskStatus(BaseModel):
    key: str
    life_cycle: str
    result: str | None = None
    display_state: str
    font_color: str
    fill_color: str
    depends_on: list[str] = []


class RunStatus(BaseModel):
    run_id: int
    life_cycle: str
    result: str | None = None
    message: str
    is_running: bool
    is_done: bool
    elapsed_seconds: int | None = None
    tasks: list[TaskStatus] = []


class JobDetail(BaseModel):
    job_id: int
    name: str
    last_run_at: str | None = None
    active_run_id: int | None = None
    parameters: list[dict] = []
    tasks: list[dict] = []


class ScraperJob(BaseModel):
    job_id: int
    name: str
    last_status: str
    last_run_at: str | None = None


class WorkflowConfig(BaseModel):
    team: str
    job_id: str
    sheet_id: str
    job_url: str
    sheet_url: str
