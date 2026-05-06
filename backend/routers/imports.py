import io
import json

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.config import get_sources_table
from backend.dependencies import get_current_user, validate_team
from backend.models.import_request import ColumnMapping, ImportRequest, ImportResult
from backend.services.gsheets import get_gsheets_client, parse_gsheet_url, read_worksheet
from backend.services.import_logic import auto_map, do_import, parse_paste

router = APIRouter(prefix="/import", tags=["imports"])


class PasteImportRequest(BaseModel):
    text: str
    import_request: ImportRequest


def _apply_row_filters(df: pd.DataFrame, row_filters_json: str) -> pd.DataFrame:
    """Filter DataFrame rows based on column→allowed_values mapping."""
    filters = json.loads(row_filters_json)
    for col, values in filters.items():
        if col in df.columns and values:
            df = df[df[col].astype(str).isin(values)]
    return df


@router.post("/csv", response_model=ImportResult)
async def import_csv(
    team: str = Depends(validate_team),
    user: str = Depends(get_current_user),
    file: UploadFile = File(...),
    mapping_json: str = Form(...),
    platform_override: str = Form("Auto-detect from URL"),
    col_hint_platform: str | None = Form(None),
    manual_values_json: str = Form("{}"),
    meta_mapping_json: str = Form("{}"),
    row_filters_json: str = Form("{}"),
):
    try:
        contents = await file.read()
        raw_df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    try:
        mapping = ColumnMapping(**json.loads(mapping_json)).model_dump()
        manual_values = json.loads(manual_values_json)
        meta_mapping = json.loads(meta_mapping_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid mapping JSON: {e}")

    raw_df = _apply_row_filters(raw_df, row_filters_json)
    table = get_sources_table(team)
    result = do_import(
        raw_df=raw_df,
        mapping=mapping,
        platform_override=platform_override,
        col_hint_platform=col_hint_platform,
        target_table=table,
        meta_mapping=meta_mapping,
        manual_values=manual_values,
        user=user,
    )
    return result


@router.post("/paste", response_model=ImportResult)
async def import_paste(
    body: PasteImportRequest,
    team: str = Depends(validate_team),
    user: str = Depends(get_current_user),
):
    raw_df = parse_paste(body.text)
    if raw_df is None or raw_df.empty:
        raise HTTPException(status_code=400, detail="Could not parse pasted data.")

    req = body.import_request
    if req.row_filters:
        raw_df = _apply_row_filters(raw_df, json.dumps(req.row_filters))
    table = get_sources_table(team)
    result = do_import(
        raw_df=raw_df,
        mapping=req.mapping.model_dump(),
        platform_override=req.platform_override,
        col_hint_platform=req.col_hint_platform,
        target_table=table,
        meta_mapping=req.meta_mapping,
        manual_values=req.manual_values,
        user=user,
    )
    return result


@router.get("/gsheet/sheets")
async def gsheet_sheets(url: str):
    try:
        spreadsheet_id, _ = parse_gsheet_url(url)
        gc = get_gsheets_client()
        spreadsheet = gc.open_by_key(spreadsheet_id)
        worksheets = spreadsheet.worksheets()
        return {
            "name": spreadsheet.title,
            "tabs": [{"id": ws.id, "title": ws.title} for ws in worksheets],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gsheet/columns")
async def gsheet_columns(id: str, gid: int):
    """Return columns and first 5 preview rows for column mapping UI."""
    try:
        data = read_worksheet(id, gid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    all_rows = data["rows"]
    suggested_mapping = auto_map(data["columns"])
    return {
        "columns": data["columns"],
        "preview": all_rows[:5],
        "all_rows": all_rows,
        "suggested_mapping": suggested_mapping,
    }


@router.post("/gsheet/import", response_model=ImportResult)
async def import_gsheet(
    team: str = Depends(validate_team),
    user: str = Depends(get_current_user),
    spreadsheet_id: str = Form(...),
    gid: int = Form(...),
    mapping_json: str = Form(...),
    platform_override: str = Form("Auto-detect from URL"),
    col_hint_platform: str | None = Form(None),
    manual_values_json: str = Form("{}"),
    meta_mapping_json: str = Form("{}"),
    row_filters_json: str = Form("{}"),
):
    try:
        data = read_worksheet(spreadsheet_id, gid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read sheet: {e}")

    if not data["columns"]:
        raise HTTPException(status_code=400, detail="Sheet is empty.")

    raw_df = pd.DataFrame(data["rows"], columns=data["columns"])

    try:
        mapping = ColumnMapping(**json.loads(mapping_json)).model_dump()
        manual_values = json.loads(manual_values_json)
        meta_mapping = json.loads(meta_mapping_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid mapping JSON: {e}")

    raw_df = _apply_row_filters(raw_df, row_filters_json)
    table = get_sources_table(team)
    return do_import(
        raw_df=raw_df,
        mapping=mapping,
        platform_override=platform_override,
        col_hint_platform=col_hint_platform,
        target_table=table,
        meta_mapping=meta_mapping,
        manual_values=manual_values,
        user=user,
    )
