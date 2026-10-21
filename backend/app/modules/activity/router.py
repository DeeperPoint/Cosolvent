"""Activity feed and audit trail.

Two readers, two audiences. The signed-in feed shows everything recorded; the
public one shows only market-level events about synthetic participants, because
a visitor to a demo has no business seeing who edited what.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.core.dependencies import get_current_user
from app.modules.profiles import repository as profiles_repo
from app.modules.activity import service

router = APIRouter()


@router.get("/activity")
async def market_activity(
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """Everything recorded, newest first."""
    return {"events": await service.market_feed(limit=limit)}


@router.get("/activity/public")
async def public_activity(limit: int = Query(50, ge=1, le=200)):
    """Market-level events only — safe for an anonymous showcase visitor."""
    return {"events": await service.market_feed(limit=limit, public_only=True)}


@router.get("/profiles/{type_slug}/{profile_id}/events")
async def profile_events(
    type_slug: str = Path(...),
    profile_id: str = Path(...),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """The audit trail of one profile: its own edits, approvals and indexing.

    Readable by the profile's owner or an admin. A participant can see what was
    done to their own record; nobody else can.
    """
    profile = await profiles_repo.get_profile_by_id(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    is_owner = str(profile.get("user_id")) == str(user.get("_id") or user.get("id"))
    is_admin = user.get("role") == "admin" or bool(user.get("is_admin"))
    if not (is_owner or is_admin):
        raise HTTPException(status_code=403, detail="Not your profile")

    return {"events": await service.subject_trail("profile", profile_id, limit=limit)}
