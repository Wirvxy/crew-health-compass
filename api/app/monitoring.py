"""Mode 1 monitoring: compare a manual check-in with personal synthetic history.

These endpoints only expose Person A's Mode 1 engine (engine/mode1_*.py):
- At application startup, load_history() reads Person B's synthetic ISS
  dataset once (data/mode1/ by default) and builds A's HistoryIndex.
- Both endpoints need a profile session (app/sessions.py, demo access control)
  and answer only for the session's astronaut.
- POST /api/monitoring/assess accepts only a JSON body. It checks the request
  with A's validate_manual_check_in(), refuses a check-in that names another
  astronaut than the session's (403), runs this API's format and logic checks
  (app/checkin_checks.py), stores the check-in and its assessment for that
  astronaut (app/storage.py), and returns A's assess_check_in() result
  unchanged. That function checks its own output with validate_assessment().
  Stored check-ins are not added to the baseline: A's engine compares every
  check-in with the synthetic history only.
- Only A's M2 statistical detection runs. The M3 Isolation Forest
  (engine/mode1_ml.py) is never imported here.

The history is SIMULATED: fictional crew roles and readings, not astronaut
telemetry. A result is an exploratory statistical comparison with that
history, not a clinical assessment, diagnosis or advice. No action guidance
is produced: next_action_protocol_id stays null until protocols are approved.

If loading fails, the application still starts. These endpoints then answer
503 with a message that names no server path, and the error is logged.

PROVISIONAL: the endpoint names and the error format wait for A's and C's
agreement (the error format is TBD at G1).
"""

import csv
import json
import logging
import os
import sqlite3
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app import storage
from app.checkin_checks import check_readings
from app.sessions import personal, same_site
from engine.mode1_contracts import CONTEXTS, validate_manual_check_in
from engine.mode1_detection import HistoryIndex, assess_check_in
from engine.mode1_ingestion import DEFAULT_DATA_PATH, load_monitoring_data

DATA_ENV_VAR = "CREW_HEALTH_MODE1_DATA"  # same variable as A's engine tests
NOTE = (
    "Synthetic history: fictional crew roles and readings, not astronaut telemetry. "
    "Results are statistical comparisons with personal history, not a clinical "
    "assessment, diagnosis or treatment advice."
)
NOT_LOADED = (
    "Mode 1 history is not loaded: the application's startup step did not run. "
    "Restart the server."
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitoring", tags=["Mode 1 monitoring (synthetic history)"])


@dataclass(frozen=True)
class Mode1Data:
    """Built once, at startup, from A's functions."""

    history: HistoryIndex
    # astronaut -> one summary per activity context: count, first and last time
    astronauts: dict[str, list[dict[str, Any]]]


@dataclass(frozen=True)
class Unavailable:
    """Why the history could not be loaded, safe to show to clients."""

    detail: str


_state: Mode1Data | Unavailable | None = None


def data_source() -> Path:
    """Folder or ZIP holding B's synthetic dataset (default: data/mode1/)."""
    value = os.environ.get(DATA_ENV_VAR)
    return Path(value) if value else DEFAULT_DATA_PATH


def _build(source: Path) -> Mode1Data:
    observations = load_monitoring_data(source)
    times: dict[tuple[str, str], list] = defaultdict(list)
    for observation in observations:
        times[observation.astronaut_id, observation.activity_context].append(observation.timestamp)
    astronauts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (astronaut, context), stamps in sorted(times.items()):
        astronauts[astronaut].append({
            "activity_context": context,
            "observations": len(stamps),
            "first": min(stamps).isoformat(),
            "last": max(stamps).isoformat(),
        })
    return Mode1Data(HistoryIndex(observations), dict(astronauts))


def load_history() -> None:
    """Load the synthetic history once. The app calls this at startup.

    It never raises for missing or unusable data: it logs the error and keeps
    a client-safe message, so the app starts and these endpoints answer 503.
    """
    global _state
    try:
        _state = _build(data_source())
    except FileNotFoundError as error:
        logger.error("Mode 1 data file missing: %s", error)
        _state = Unavailable(
            "Mode 1 synthetic history not found. Put Person B's iss-synthetic-3000 "
            f"folder or ZIP where {DATA_ENV_VAR} points (default: the repository's "
            "data/mode1/ folder), then restart the server."
        )
    except (OSError, ValueError, csv.Error, zipfile.BadZipFile):
        logger.exception("Mode 1 synthetic history could not be read")
        _state = Unavailable(
            "Mode 1 synthetic history could not be read. Check Person B's "
            "iss-synthetic-3000 files, then restart the server."
        )
    else:
        logger.info("Loaded Mode 1 history for %d astronauts", len(_state.astronauts))


def clear_history() -> None:
    """Forget the loaded history (at shutdown, and between tests)."""
    global _state
    _state = None


def _loaded() -> Mode1Data:
    state = _state
    if isinstance(state, Mode1Data):
        return state
    raise HTTPException(
        status_code=503,
        detail=state.detail if isinstance(state, Unavailable) else NOT_LOADED,
    )


def astronaut_ids() -> list[str]:
    """The crew IDs of the synthetic history: the profiles a session can be opened for."""
    return sorted(_loaded().astronauts)


@router.get("/astronauts")
def list_astronauts(astronaut: str = Depends(personal)) -> dict[str, Any]:
    """The signed-in astronaut, with the time range of their history in each context.

    A check-in is compared only with earlier readings of the same astronaut in
    the same context, so demo check-ins need a timestamp after enough history.
    Other astronauts' history is personal to them and is not listed.
    """
    data = _loaded()
    return {
        "data_origin": "synthetic",
        "provenance": "simulated",
        "note": NOTE,
        "manual_contexts": sorted(CONTEXTS),
        "astronauts": [{"astronaut_id": astronaut, "history": data.astronauts[astronaut]}],
    }


@router.post("/assess")
async def assess(request: Request, astronaut: str = Depends(personal)) -> dict[str, Any]:
    """Assess one manual check-in with A's M2 statistical detection, and store it.

    Errors use one shape, {"detail": "<message>"}: 401 without a profile
    session, 403 for a check-in naming another astronaut or sent from another
    website, 415 when the body is not sent as JSON, 422 for an invalid
    check-in, 503 when the history is not loaded or the check-in cannot be saved.
    """
    data = _loaded()
    same_site(request)
    # Only JSON is accepted. Another website can make a visitor's browser send a
    # text/plain or form POST here without asking this server first. For a JSON
    # POST, the browser must ask first (a CORS preflight), and this API never
    # says yes, so such a request from another site is never sent.
    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if media_type != "application/json":
        raise HTTPException(
            415, "Send the check-in as JSON, with the header Content-Type: application/json."
        )
    try:
        # Numbers sent as JSON numbers keep their exact digits as Decimals.
        payload = json.loads(await request.body(), parse_float=Decimal)
    except RecursionError:  # brackets nested thousands of levels deep
        raise HTTPException(422, "Invalid check-in: the JSON is nested too deeply.") from None
    except ValueError:  # also covers bodies that are not UTF-8
        raise HTTPException(422, "Invalid check-in: the request body must be JSON.") from None
    try:
        check_in = validate_manual_check_in(payload)
    except ValueError as error:
        raise HTTPException(422, f"Invalid check-in: {error}") from None
    # The session decides whose check-in this is. The body must agree, so a
    # request cannot add a check-in to another astronaut's history.
    if check_in["astronaut_id"] != astronaut:
        raise HTTPException(403, "This check-in names another astronaut than your profile.")
    try:
        check_readings(payload["indicators"], check_in["indicators"])
    except ValueError as error:
        raise HTTPException(422, f"Invalid check-in: {error}") from None
    result = assess_check_in(check_in, data.history)
    try:
        storage.save_checkin(astronaut, check_in, result)
    except sqlite3.Error:
        logger.exception("Check-in could not be saved")
        raise HTTPException(503, "The check-in was assessed but could not be saved. Try again.") from None
    return result
