"""Demo access control: profile sessions (no passwords, by the team's choice).

Choosing a crew profile on the start page opens a session for that astronaut. The
browser keeps only a random session ID in a cookie that page scripts cannot read
(HttpOnly). The server stores the ID's SHA-256 hash, never the ID itself. Every
personal endpoint takes the astronaut from the session, never from the request.

What this does:
- keeps the four workspaces apart: one profile's check-ins, results and plan never
  appear in another profile's screens or API answers;
- ends the session on logout (the server forgets it, so the cookie stops working);
- refuses data changes sent from another website (SameSite=Strict cookie, and a
  check of the browser's Sec-Fetch-Site header).

What it does not do: prove who is at the keyboard. There are no passwords, so anyone
who can open the app can choose any profile. Call it demo access control, not
account security.
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from app import monitoring, storage
from app.db import transaction

COOKIE = "chc_session"
SESSION_HOURS = 12
PROFILE_HEADER = "X-Crew-Health-Profile"  # on personal answers, so the browser can check whose data it got
SECURE_ENV_VAR = "CREW_HEALTH_COOKIE_SECURE"  # "auto" (default), "true" or "false"
NO_SESSION = "Choose a crew profile first."

router = APIRouter(prefix="/api", tags=["Profiles and sessions (demo access control)"])


def profile(astronaut_id: str) -> dict[str, str]:
    """A crew profile as the start page shows it: "flight_engineer_1" -> "Flight Engineer 1"."""
    return {"astronaut_id": astronaut_id, "name": astronaut_id.replace("_", " ").title()}


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def same_site(request: Request) -> None:
    """Refuse a data change that a page on another website made the browser send.

    Browsers add Sec-Fetch-Site to every request, and a web page cannot change it.
    Clients that are not browsers (tests, curl) do not send it; they are not the
    cross-site risk this check is about.
    """
    site = request.headers.get("sec-fetch-site")
    if site is not None and site not in ("same-origin", "none"):
        raise HTTPException(403, "Requests from another website cannot change data here.")


def require_json(request: Request) -> None:
    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if media_type != "application/json":
        raise HTTPException(415, "Send the request as JSON, with the header Content-Type: application/json.")


def _secure(request: Request) -> bool:
    """Secure cookies are sent over HTTPS only. "auto" follows the request's scheme."""
    setting = os.environ.get(SECURE_ENV_VAR, "auto").strip().lower()
    if setting in ("true", "1", "yes"):
        return True
    if setting in ("false", "0", "no"):
        return False
    return request.url.scheme == "https"


def session_astronaut(request: Request) -> str | None:
    """The astronaut of a valid session cookie, or None. Expired sessions are deleted."""
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    key = hash_token(token)
    with transaction() as conn:
        storage.migrate(conn)
        row = conn.execute("SELECT astronaut_id, expires_at FROM sessions WHERE token_hash = ?", (key,)).fetchone()
        if row and row[1] <= storage.now():
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (key,))
            row = None
    return row[0] if row else None


def personal(request: Request, response: Response) -> str:
    """Dependency for every personal endpoint: the signed-in astronaut, or 401.

    Personal answers are never stored by the browser cache, and they name their
    owner in a header so the frontend can drop an answer meant for another profile.
    """
    astronaut = session_astronaut(request)
    if astronaut is None:
        raise HTTPException(401, NO_SESSION)
    response.headers["Cache-Control"] = "no-store"
    response.headers[PROFILE_HEADER] = astronaut
    return astronaut


@router.get("/profiles")
def list_profiles() -> dict[str, Any]:
    """The crew profiles a session can be opened for: the synthetic history's crew roles."""
    return {
        "profiles": [profile(a) for a in monitoring.astronaut_ids()],
        "note": "Fictional crew roles from the synthetic history. Choosing one is demo access control: there are no passwords.",
    }


@router.get("/session")
def current_session(request: Request, response: Response) -> dict[str, Any]:
    """The profile of this browser's session: {"profile": {...}}, or {"profile": null} when signed out.

    Being signed out is a normal answer here (200), not an error; personal endpoints answer 401.
    """
    response.headers["Cache-Control"] = "no-store"
    astronaut = session_astronaut(request)
    return {"profile": profile(astronaut) if astronaut else None}


@router.post("/session")
async def open_session(request: Request, response: Response) -> dict[str, str]:
    """Open a session for the chosen profile. Any earlier session of this browser ends."""
    same_site(request)
    require_json(request)
    try:
        body = await request.json()
    except (ValueError, RecursionError):
        raise HTTPException(422, "The request body must be JSON.") from None
    astronaut = body.get("astronaut_id") if isinstance(body, dict) else None
    if not isinstance(astronaut, str) or astronaut not in monitoring.astronaut_ids():
        raise HTTPException(422, f"Unknown crew profile. Profiles: {', '.join(monitoring.astronaut_ids())}.")
    token, created = secrets.token_urlsafe(32), datetime.now(timezone.utc)
    with transaction() as conn:
        storage.migrate(conn)
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (storage.now(),))
        old = request.cookies.get(COOKIE)
        if old:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(old),))
        conn.execute(
            "INSERT INTO sessions (token_hash, astronaut_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (hash_token(token), astronaut, created.isoformat(timespec="seconds"),
             (created + timedelta(hours=SESSION_HOURS)).isoformat(timespec="seconds")),
        )
    response.set_cookie(COOKIE, token, max_age=SESSION_HOURS * 3600, path="/", httponly=True,
                        samesite="strict", secure=_secure(request))
    response.headers["Cache-Control"] = "no-store"
    return profile(astronaut)


@router.delete("/session")
def end_session(request: Request, response: Response) -> dict[str, bool]:
    """Log out: the server forgets the session, and the cookie is removed."""
    same_site(request)
    token = request.cookies.get(COOKIE)
    if token:
        with transaction() as conn:
            storage.migrate(conn)
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict", secure=_secure(request))
    response.headers["Cache-Control"] = "no-store"
    return {"signed_out": True}
