from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_current_user, validate_team
from backend.models.sync_config import SyncConfig, SyncConfigCreate, SyncConfigUpdate, SyncResult
from backend.services.sync_config import (
    create_sync_config,
    delete_sync_config,
    get_sync_config,
    list_sync_configs,
    run_sync_for_config,
    update_sync_config,
)

router = APIRouter(prefix="/sync-configs", tags=["sync-configs"])


@router.get("", response_model=list[SyncConfig])
async def list_configs(team: str = Depends(validate_team)):
    return list_sync_configs(team)


@router.post("", response_model=dict)
async def create_config(
    body: SyncConfigCreate,
    team: str = Depends(validate_team),
    user: str = Depends(get_current_user),
):
    config_id = create_sync_config(
        spreadsheet_id=body.spreadsheet_id,
        spreadsheet_url=body.spreadsheet_url,
        spreadsheet_name=body.spreadsheet_name,
        tab_title=body.tab_title,
        gid=body.gid,
        team=body.team,
        mapping_json=body.mapping_json,
        platform_override=body.platform_override,
        manual_values_json=body.manual_values_json,
        meta_mapping_json=body.meta_mapping_json,
        sync_interval_minutes=body.sync_interval_minutes,
        user=user,
    )
    return {"id": config_id}


@router.patch("/{config_id}")
async def patch_config(config_id: str, body: SyncConfigUpdate):
    existing = get_sync_config(config_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Sync config not found")
    updates = body.model_dump(exclude_none=True)
    if updates:
        update_sync_config(config_id, updates)
    return {"ok": True}


@router.delete("/{config_id}")
async def remove_config(config_id: str):
    delete_sync_config(config_id)
    return {"ok": True}


@router.post("/{config_id}/sync", response_model=SyncResult)
async def trigger_sync(config_id: str):
    config = get_sync_config(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Sync config not found")
    return run_sync_for_config(config)
