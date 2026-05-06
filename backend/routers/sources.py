import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.config import detect_platform_from_url, get_sources_table
from backend.dependencies import get_current_user, validate_team
from backend.models.source import DailyCount, DashboardData, DeleteRequest, Source, SourceCreate, SourcesPage
from backend.services.sources import (
    build_filter_where,
    count_sources_filtered,
    delete_sources_by_ids,
    get_dashboard_data,
    get_filter_options,
    insert_source,
    load_sources,
    load_sources_page,
    wipe_all_sources,
)

router = APIRouter(prefix="/sources", tags=["sources"])

PAGE_SIZE_MAX = 500


@router.get("/filter-options")
async def list_filter_options(team: str = Depends(validate_team)):
    """Return distinct non-empty values for each filterable categorical column."""
    table = get_sources_table(team)
    return get_filter_options(table)


@router.get("", response_model=SourcesPage)
async def list_sources(
    team: str = Depends(validate_team),
    platform: str | None = None,
    keyword: str | None = None,
    abuse_area: str | None = None,
    sub_abuse_area: str | None = None,
    relevancy: str | None = None,
    added_by: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    table = get_sources_table(team)
    where = build_filter_where(platform, keyword, abuse_area, sub_abuse_area, relevancy, added_by)
    total = count_sources_filtered(table, where)
    df = load_sources_page(table, where, min(limit, PAGE_SIZE_MAX), offset)
    items = df.where(df.notna(), None).to_dict(orient="records") if not df.empty else []
    return {"items": items, "total": total}


@router.post("", response_model=Source)
async def add_source(
    body: SourceCreate,
    team: str = Depends(validate_team),
    user: str = Depends(get_current_user),
):
    if not body.url.strip():
        raise HTTPException(status_code=400, detail="URL is required")

    platform = (
        detect_platform_from_url(body.url)
        if body.auto_detect_platform or not body.platform
        else body.platform
    )

    table = get_sources_table(team)
    insert_source(
        table=table,
        url=body.url.strip(),
        platform=platform,
        team=team,
        abuse_area=body.abuse_area,
        sub_abuse_area=body.sub_abuse_area,
        notes=body.notes,
        relevancy=body.relevancy,
        user=user,
    )

    df = load_sources(table)
    row = df[df["url"] == body.url.strip()]
    if row.empty:
        raise HTTPException(status_code=500, detail="Source was inserted but could not be retrieved")
    return row.iloc[0].where(row.iloc[0].notna(), None).to_dict()


@router.delete("")
async def delete_sources(
    body: DeleteRequest,
    team: str = Depends(validate_team),
):
    if not body.ids:
        raise HTTPException(status_code=400, detail="No IDs provided")
    table = get_sources_table(team)
    delete_sources_by_ids(table, body.ids)
    return {"deleted": len(body.ids)}


@router.delete("/wipe-all")
async def wipe_all(
    team: str = Depends(validate_team),
    user: str = Depends(get_current_user),
):
    if team != "TEST":
        raise HTTPException(status_code=403, detail="Wipe all is only allowed for the TEST team")
    table = get_sources_table(team)
    deleted = wipe_all_sources(table)
    return {"deleted": deleted}


@router.get("/export")
async def export_sources(
    team: str = Depends(validate_team),
    platform: str | None = None,
    keyword: str | None = None,
    abuse_area: str | None = None,
    sub_abuse_area: str | None = None,
    relevancy: str | None = None,
    added_by: str | None = None,
):
    table = get_sources_table(team)
    where = build_filter_where(platform, keyword, abuse_area, sub_abuse_area, relevancy, added_by)
    # Export pulls all matching rows (no pagination)
    from backend.services.sources import run_query
    df = run_query(f"SELECT * FROM {table} WHERE {where} ORDER BY added_at DESC")

    csv_bytes = df.to_csv(index=False).encode()
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="sources_{team}.csv"'},
    )


@router.get("/dashboard", response_model=DashboardData)
async def get_dashboard(team: str = Depends(validate_team)):
    table = get_sources_table(team)
    data = get_dashboard_data(table)
    data["daily_counts"] = [DailyCount(**d) for d in data["daily_counts"]]
    return data
