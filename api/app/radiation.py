"""Mission Environment: historical Mars radiation measured by Curiosity's RAD (R1).

These read-only endpoints only expose Iliass Barrou's engine
(engine/radiation_history.py):
- At application startup, load_history() reads the local RAD CSV once, with
  its path passed explicitly, and keeps the parsed history.
- The endpoints return radiation_timeline() and may_20_event_summary() output
  unchanged. Nothing is recalculated here, and nothing is downloaded.

The values describe the Martian radiation environment at one detector. They
are not a personal astronaut exposure or a medical risk, and they never
affect the Mode 1 health assessment or the Mode 2 passport.

If loading fails, the application still starts. These endpoints then answer
503 with a message that names no server path, and the error is logged.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from engine.radiation_history import (
    DEFAULT_CSV_PATH,
    RadiationHistory,
    load_radiation_history,
    may_20_event_summary,
    radiation_timeline,
)

DATA_ENV_VAR = "CREW_HEALTH_RAD_CSV"  # same variable as the engine tests
NOT_LOADED = (
    "Radiation history is not loaded: the application's startup step did not run. "
    "Restart the server."
)

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/environment/radiation",
    tags=["Mission Environment (historical radiation)"],
)


@dataclass(frozen=True)
class RadiationData:
    """Built once, at startup, from the engine's loader."""

    history: RadiationHistory
    detectors: tuple[str, ...]  # detector IDs present in the CSV, for clear 404s


@dataclass(frozen=True)
class Unavailable:
    """Why the CSV could not be loaded, safe to show to clients."""

    detail: str


_state: RadiationData | Unavailable | None = None


def data_path() -> Path:
    """The RAD CSV (default: the repository's data/radiation/)."""
    value = os.environ.get(DATA_ENV_VAR)
    return Path(value) if value else DEFAULT_CSV_PATH


def load_history() -> None:
    """Load the CSV once. The app calls this at startup.

    It never raises for a missing or unusable file: it logs the error and
    keeps a client-safe message, so the app starts and these endpoints
    answer 503.
    """
    global _state
    try:
        history = load_radiation_history(data_path())
    except FileNotFoundError as error:
        logger.error("Radiation CSV missing: %s", error)
        _state = Unavailable(
            "Radiation history not found. Put the Curiosity RAD CSV in the repository's "
            f"'data/radiation/' folder or set {DATA_ENV_VAR}, "
            "then restart the server."
        )
    except (OSError, ValueError):  # ValueError also covers bad encoding and bad rows
        logger.exception("Radiation CSV could not be read")
        _state = Unavailable(
            "Radiation history could not be read. Check the Curiosity RAD CSV, "
            "then restart the server."
        )
    else:
        detectors = tuple(sorted({row.detector for row in history.observations}))
        _state = RadiationData(history, detectors)
        logger.info(
            "Loaded radiation history: %d observations, detectors %s",
            len(history.observations), ", ".join(detectors),
        )


def clear_history() -> None:
    """Forget the loaded history (at shutdown, and between tests)."""
    global _state
    _state = None


def _loaded() -> RadiationData:
    state = _state
    if isinstance(state, RadiationData):
        return state
    raise HTTPException(
        status_code=503,
        detail=state.detail if isinstance(state, Unavailable) else NOT_LOADED,
    )


def _check_detector(data: RadiationData, detector: str | None) -> None:
    if detector is not None and detector not in data.detectors:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown detector {detector!r}. Available detectors: {', '.join(data.detectors)}.",
        )


@router.get("/timeline")
def timeline(
    start_date: str | None = None,
    end_date: str | None = None,
    detector: str | None = None,
    include_statistics: bool = False,
) -> dict[str, Any]:
    """Chronological RAD readings, optionally filtered by inclusive UTC dates (YYYY-MM-DD).

    Returns the engine's radiation_timeline() output unchanged: decimal
    strings, null for missing readings, the unit and the CSV's SHA-256.
    """
    data = _loaded()
    _check_detector(data, detector)
    try:
        return radiation_timeline(
            data.history, start_date=start_date, end_date=end_date,
            detector=detector, include_statistics=include_statistics,
        )
    except ValueError as error:  # bad date format, impossible date, or start after end
        raise HTTPException(status_code=422, detail=f"Invalid date filter: {error}") from None


@router.get("/events/may-20-2024")
def may_20_2024_event(detector: str | None = None) -> dict[str, Any]:
    """Readings on 2024-05-20 (NASA's documented solar event) and the week before.

    Returns the engine's may_20_event_summary() output unchanged.
    """
    data = _loaded()
    _check_detector(data, detector)
    return may_20_event_summary(data.history, detector=detector)
