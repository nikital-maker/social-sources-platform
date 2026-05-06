from pydantic import BaseModel


class SheetTab(BaseModel):
    id: int
    title: str


class SheetData(BaseModel):
    columns: list[str]
    rows: list[list[str]]


class SheetUpdateRequest(BaseModel):
    sheet_id: str
    tab_title: str
    rows: list[list[str]]


class TabRenameRequest(BaseModel):
    sheet_id: str
    old_title: str
    new_title: str
