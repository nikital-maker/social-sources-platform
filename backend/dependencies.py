from fastapi import HTTPException, Request

from backend.config import TEAMS
from backend.services.databricks_client import current_user, get_workspace_client


async def get_current_user(request: Request) -> str:
    # Databricks Apps injects the authenticated user via a header
    user = request.headers.get("X-Databricks-User") or request.headers.get("X-Forwarded-User")
    if user:
        return user
    return current_user()


def validate_team(team: str) -> str:
    if team not in TEAMS:
        raise HTTPException(status_code=404, detail=f"Unknown team: {team!r}")
    return team
