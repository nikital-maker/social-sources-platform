from fastapi import APIRouter, HTTPException

from backend.models.gsheet import SheetData, SheetTab, SheetUpdateRequest, TabRenameRequest
from backend.services.gsheets import (
    list_worksheets,
    parse_gsheet_url,
    read_worksheet,
    rename_worksheet,
    write_worksheet,
)

router = APIRouter(prefix="/gsheets", tags=["gsheets"])


@router.get("/sheets", response_model=list[SheetTab])
async def get_sheets(url: str):
    try:
        spreadsheet_id, _ = parse_gsheet_url(url)
        return list_worksheets(spreadsheet_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data", response_model=SheetData)
async def get_sheet_data(id: str, gid: int):
    try:
        return read_worksheet(id, gid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/data")
async def update_sheet_data(body: SheetUpdateRequest):
    try:
        saved = write_worksheet(body.sheet_id, body.tab_title, body.rows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"saved_rows": saved}


@router.patch("/tab")
async def rename_tab(body: TabRenameRequest):
    try:
        rename_worksheet(body.sheet_id, body.old_title, body.new_title)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}
