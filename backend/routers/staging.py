from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.config import get_sources_table
from backend.dependencies import get_current_user, validate_team
from backend.models.source import Source
from backend.services.staging import approve_staged, load_staging, reject_staged

router = APIRouter(prefix="/staging", tags=["staging"])


class StagingAction(BaseModel):
    url: str


@router.get("", response_model=list[Source])
async def list_staging(team: str = Depends(validate_team)):
    table = get_sources_table(team)
    df = load_staging(table)
    if df.empty:
        return []
    return df.where(df.notna(), None).to_dict(orient="records")


@router.post("/approve")
async def approve(
    body: StagingAction,
    team: str = Depends(validate_team),
    user: str = Depends(get_current_user),
):
    table = get_sources_table(team)
    # Load the row to get all its fields
    from backend.services.staging import load_staging

    df = load_staging(table)
    row_df = df[df["url"] == body.url]
    if row_df.empty:
        raise HTTPException(status_code=404, detail="Staging row not found")
    row = row_df.iloc[0].where(row_df.iloc[0].notna(), None).to_dict()
    approve_staged(row, table, user)
    return {"ok": True}


@router.post("/reject")
async def reject(body: StagingAction):
    reject_staged(body.url)
    return {"ok": True}
