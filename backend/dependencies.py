from fastapi import HTTPException, Request

from backend.config import TEAMS
from backend.services.databricks_client import current_user, get_workspace_client


async def get_current_user(request: Request) -> str:
    for header in (
        "X-Forwarded-Email",
        "X-Forwarded-Preferred-Username",
        "X-Databricks-User",
        "X-Forwarded-User",
    ):
        val = request.headers.get(header)
        if val and "@" in val:
            return val
    return current_user()


def validate_team(team: str) -> str:
    if team not in TEAMS:
        raise HTTPException(status_code=404, detail=f"Unknown team: {team!r}")
    return team
