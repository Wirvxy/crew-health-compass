"""Personal workspace endpoints: the signed-in astronaut's own check-ins and daily plan.

Every endpoint needs a profile session (401 without one) and reads or writes only
the rows owned by the session's astronaut. No endpoint takes an astronaut ID from
the URL, the query or the body, so a request cannot point at another profile.
"""

import re
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app import storage
from app.sessions import personal, require_json, same_site

router = APIRouter(prefix="/api/me", tags=["Personal workspace (demo access control)"])
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


def _day(value: str) -> str:
    """A UTC day as YYYY-MM-DD. The browser sends its own UTC date, so the plan resets at 00:00 UTC."""
    try:
        if _DAY.fullmatch(value) and date.fromisoformat(value):
            return value
    except ValueError:
        pass
    raise HTTPException(422, "day must be a date written as YYYY-MM-DD.")


@router.get("/checkins")
def my_checkins(limit: int = Query(10, ge=1, le=50), astronaut: str = Depends(personal)) -> dict[str, Any]:
    """The signed-in astronaut's stored check-ins and their assessments, newest first."""
    return {"astronaut_id": astronaut, "checkins": storage.list_checkins(astronaut, limit)}


@router.get("/plan")
def my_plan(day: str, astronaut: str = Depends(personal)) -> dict[str, Any]:
    """The signed-in astronaut's "Plan for today" for one UTC day."""
    return storage.plan_for(astronaut, _day(day))


@router.put("/plan/review")
async def mark_review(request: Request, astronaut: str = Depends(personal)) -> dict[str, Any]:
    """Tick or untick "Review today's result": {"day": "YYYY-MM-DD", "done": true}."""
    same_site(request)
    require_json(request)
    try:
        body = await request.json()
    except (ValueError, RecursionError):
        raise HTTPException(422, "The request body must be JSON.") from None
    if not isinstance(body, dict) or set(body) != {"day", "done"} or not isinstance(body["done"], bool) \
            or not isinstance(body["day"], str):
        raise HTTPException(422, 'Send {"day": "YYYY-MM-DD", "done": true or false}.')
    day = _day(body["day"])
    storage.set_plan_mark(astronaut, day, "review", body["done"])
    return storage.plan_for(astronaut, day)
