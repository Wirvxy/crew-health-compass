"""Mode 1 monitoring: compare a manual check-in with personal synthetic history.

These endpoints only expose Person A's Mode 1 engine (engine/mode1_*.py):
- At application startup, load_history() reads Person B's synthetic ISS
  dataset once (iss-synthetic-3000/ by default) and builds A's HistoryIndex.
- POST /api/monitoring/assess checks the request with A's
  validate_manual_check_in() and returns A's assess_check_in() result
  unchanged. That function checks its own output with validate_assessment().
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
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

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
    """Folder or ZIP holding B's synthetic dataset (default: iss-synthetic-3000/)."""
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
            "iss-synthetic-3000/ folder), then restart the server."
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


@router.get("/astronauts")
def list_astronauts() -> dict[str, Any]:
    """Synthetic crew IDs, with the time range of their history in each context.

    A check-in is compared only with earlier readings of the same astronaut in
    the same context, so demo check-ins need a timestamp after enough history.
    """
    data = _loaded()
    return {
        "data_origin": "synthetic",
        "provenance": "simulated",
        "note": NOTE,
        "manual_contexts": sorted(CONTEXTS),
        "astronauts": [
            {"astronaut_id": astronaut, "history": contexts}
            for astronaut, contexts in sorted(data.astronauts.items())
        ],
    }


@router.post("/assess")
async def assess(request: Request) -> dict[str, Any]:
    """Assess one manual check-in with A's M2 statistical detection.

    Errors use one shape, {"detail": "<message>"}: 422 for an invalid
    check-in, 503 when the history is not loaded.
    """
    data = _loaded()
    try:
        # Numbers sent as JSON numbers keep their exact digits as Decimals.
        payload = json.loads(await request.body(), parse_float=Decimal)
    except ValueError:  # also covers bodies that are not UTF-8
        raise HTTPException(422, "Invalid check-in: the request body must be JSON.") from None
    try:
        check_in = validate_manual_check_in(payload)
    except ValueError as error:
        raise HTTPException(422, f"Invalid check-in: {error}") from None
    if check_in["astronaut_id"] not in data.astronauts:
        raise HTTPException(
            422,
            f"Invalid check-in: unknown astronaut_id {check_in['astronaut_id']!r}. "
            f"Known IDs: {', '.join(sorted(data.astronauts))}.",
        )
    return assess_check_in(check_in, data.history)
