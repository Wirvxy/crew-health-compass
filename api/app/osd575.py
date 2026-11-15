"""Read-only endpoints for the NASA OSD-575 serum dataset.

These endpoints only expose Person A's engine (engine/nasa_ingestion.py,
engine/biomarker_analysis.py, engine/trajectory_analysis.py and
engine/biological_passport.py):
- At application startup, load_dataset() reads the local CSV files once and
  runs A's postflight (A2) and trajectory (A3) analyses.
- The endpoints return A's serializer output unchanged. The A4 passport is
  built from those cached A2 and A3 results.
- No calculation is repeated here, and nothing is downloaded at runtime.

If loading fails, the application still starts and /health still works. The
dataset endpoints then answer 503 with a message that names the problem
without any server path, and the full error is logged. After the data files
are fixed, the server must be restarted to load them.

The results are descriptive laboratory comparisons, not clinical alerts,
diagnoses or advice. Trajectory classifications (closer, farther, mixed)
describe distance from a person's own preflight average; they are not risk
scores. These endpoints are separate from the daily check-in data that the
rest of the API will store.

PROVISIONAL: the response envelopes and error messages are not in the shared
contracts yet (the error format is TBD at G1). The trajectory and comparison
shapes wait for C's confirmation.
"""

import csv
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from engine.biological_passport import build_biological_passport
from engine.biomarker_analysis import (
    BiomarkerAnalysis,
    analyze_postflight,
    group_measurements,
    serialize_analysis,
)
from engine.nasa_ingestion import (
    DEFAULT_DATA_DIR,
    STUDY_ID,
    Panel,
    SerumMeasurement,
    load_osd575,
    serialize_measurement,
)
from engine.trajectory_analysis import (
    BiomarkerTrajectory,
    analyze_trajectories,
    compare_astronauts,
    serialize_trajectory,
)

DATA_DIR_ENV_VAR = "CREW_HEALTH_OSD575_DIR"
PROVENANCE = "dataset:OSD-575"
NOTE = (
    "Descriptive comparison of NASA OSD-575 laboratory data. "
    "Not a clinical assessment, diagnosis or treatment advice."
)
CLASSIFICATION_NOTE = (
    "trajectory_classification describes how the distance from this person's "
    "own preflight average changed across postflight visits. It is not a risk score."
)
NOT_LOADED = (
    "OSD-575 dataset is not loaded: the application's startup step did not run. "
    "Restart the server."
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/datasets/osd575", tags=["NASA OSD-575 (descriptive)"])

SeriesKey = tuple[str, str, str]  # (crew_id, panel, biomarker)


@dataclass(frozen=True)
class Osd575Data:
    """Lookup tables built once, at startup, from A's functions."""

    measurements: dict[SeriesKey, list[SerumMeasurement]]
    analyses: dict[SeriesKey, list[BiomarkerAnalysis]]
    trajectories: dict[SeriesKey, BiomarkerTrajectory]
    comparisons: dict[tuple[str, str], list[BiomarkerTrajectory]]  # (panel, biomarker)
    crew_visits: dict[str, list[str]]  # crew -> visit codes in time order
    panels: dict[str, dict[str, Any]]  # panel -> {"group": ..., "units": {biomarker: unit}}


@dataclass(frozen=True)
class Unavailable:
    """Why the dataset could not be loaded, safe to show to clients."""

    detail: str


_state: Osd575Data | Unavailable | None = None


def data_dir() -> Path:
    """Folder holding the four TRANSFORMED CSVs (default: repository data/mode2/)."""
    value = os.environ.get(DATA_DIR_ENV_VAR)
    return Path(value) if value else DEFAULT_DATA_DIR


def _build(directory: Path) -> Osd575Data:
    rows = load_osd575(directory)
    measurements = {
        key: sorted(series, key=lambda row: (row.phase_day, row.source_sample_id))
        for key, series in group_measurements(rows).items()
    }
    analysis_list = analyze_postflight(rows)
    analyses: dict[SeriesKey, list[BiomarkerAnalysis]] = defaultdict(list)
    for result in analysis_list:
        analyses[result.crew_id, result.panel, result.biomarker].append(result)

    trajectory_list = analyze_trajectories(analysis_list)
    trajectories = {(t.crew_id, t.panel, t.biomarker): t for t in trajectory_list}
    by_biomarker: dict[tuple[str, str], list[BiomarkerTrajectory]] = defaultdict(list)
    for trajectory in trajectory_list:
        by_biomarker[trajectory.panel, trajectory.biomarker].append(trajectory)
    comparisons = {
        (panel, biomarker): compare_astronauts(series, panel=panel, biomarker=biomarker)
        for (panel, biomarker), series in by_biomarker.items()
    }

    visit_days: dict[str, dict[str, int]] = defaultdict(dict)
    panels: dict[str, dict[str, Any]] = {}
    for row in rows:
        visit_days[row.crew_id][row.visit] = row.phase_day
        panel = panels.setdefault(row.panel, {"group": row.group, "units": {}})
        if panel["units"].setdefault(row.biomarker, row.unit) != row.unit:
            raise ValueError(f"{row.panel}/{row.biomarker} has more than one unit")
    crew_visits = {
        crew: sorted(days, key=days.__getitem__) for crew, days in visit_days.items()
    }
    return Osd575Data(
        measurements, dict(analyses), trajectories, comparisons, crew_visits, panels
    )


def load_dataset() -> None:
    """Load and analyse the dataset once. The app calls this at startup.

    It never raises for missing or unusable data: it logs the error and keeps
    a client-safe message, so /health keeps working and the dataset endpoints
    answer 503. Fixing the files requires restarting the server.
    """
    global _state
    try:
        _state = _build(data_dir())
    except FileNotFoundError as error:
        logger.error("OSD-575 data file missing: %s", error.filename)
        name = Path(error.filename).name if error.filename else "a required file"
        _state = Unavailable(
            f"OSD-575 data file not found: {name}. Put the four OSD-575 "
            f"TRANSFORMED CSV files in the folder set by {DATA_DIR_ENV_VAR} "
            "(default: the repository's data/mode2/ folder), then restart the "
            "server. Nothing is downloaded at runtime."
        )
    except (OSError, ValueError, csv.Error, UnicodeDecodeError):
        logger.exception("OSD-575 data files could not be read or analysed")
        _state = Unavailable(
            "OSD-575 data files could not be read or analysed. Check that they "
            "are the original NASA TRANSFORMED CSV files, then restart the server."
        )
    else:
        logger.info(
            "Loaded OSD-575 dataset: %d postflight series, %d trajectories",
            len(_state.analyses),
            len(_state.trajectories),
        )


def clear_dataset() -> None:
    """Forget the loaded dataset (at shutdown, and between tests)."""
    global _state
    _state = None


def _loaded() -> Osd575Data:
    state = _state
    if isinstance(state, Osd575Data):
        return state
    raise HTTPException(
        status_code=503,
        detail=state.detail if isinstance(state, Unavailable) else NOT_LOADED,
    )


def _envelope() -> dict[str, Any]:
    return {"study_id": STUDY_ID, "provenance": PROVENANCE, "note": NOTE}


def _check_crew(data: Osd575Data, crew_id: str) -> None:
    if crew_id not in data.crew_visits:
        raise HTTPException(status_code=404, detail=f"Unknown crew ID: {crew_id!r}")


def _select_biomarkers(data: Osd575Data, panel: str, biomarker: str | None) -> list[str]:
    units = data.panels[panel]["units"]
    if biomarker is None:
        return sorted(units)
    if biomarker not in units:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown biomarker {biomarker!r} in panel {panel!r}",
        )
    return [biomarker]


@router.get("/astronauts")
def list_astronauts() -> dict[str, Any]:
    """Crew IDs in the dataset, each with its visit codes in time order."""
    data = _loaded()
    return {
        **_envelope(),
        "astronauts": [
            {"crew_id": crew, "visits": visits}
            for crew, visits in sorted(data.crew_visits.items())
        ],
    }


@router.get("/panels")
def list_panels() -> dict[str, Any]:
    """The four panels, each with its biomarkers and their units."""
    data = _loaded()
    return {
        **_envelope(),
        "panels": [
            {
                "panel": panel,
                "group": info["group"],
                "biomarkers": [
                    {"biomarker": name, "unit": unit}
                    for name, unit in sorted(info["units"].items())
                ],
            }
            for panel, info in data.panels.items()
        ],
    }


@router.get("/astronauts/{crew_id}/measurements")
def crew_measurements(
    crew_id: str, panel: Panel, biomarker: str | None = None
) -> dict[str, Any]:
    """All visits (preflight and postflight) for one crew member and panel.

    Each record is A's serialize_measurement() output: values as exact
    strings, unavailable values as null, with units and CSV provenance.
    """
    data = _loaded()
    _check_crew(data, crew_id)
    names = _select_biomarkers(data, panel, biomarker)
    records = [
        serialize_measurement(row)
        for name in names
        for row in data.measurements.get((crew_id, panel, name), [])
    ]
    return {
        **_envelope(),
        "crew_id": crew_id,
        "panel": panel,
        "biomarker": biomarker,
        "count": len(records),
        "measurements": records,
    }


@router.get("/astronauts/{crew_id}/postflight")
def crew_postflight(
    crew_id: str,
    panel: Panel,
    biomarker: str | None = None,
    visit: str | None = None,
) -> dict[str, Any]:
    """A's postflight comparison with the personal preflight baseline.

    Each record is A's serialize_analysis() output, unchanged.
    """
    data = _loaded()
    _check_crew(data, crew_id)
    names = _select_biomarkers(data, panel, biomarker)
    results = [
        result for name in names for result in data.analyses.get((crew_id, panel, name), [])
    ]
    if visit is not None:
        results = [result for result in results if result.visit == visit]
        if not results:
            postflight = [v for v in data.crew_visits[crew_id] if v.startswith("R")]
            hint = " In URLs, write '+' as %2B (R%2B1)." if " " in visit else ""
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No postflight result for visit {visit!r}. Postflight visits "
                    f"for {crew_id}: {', '.join(postflight)}.{hint}"
                ),
            )
    return {
        **_envelope(),
        "crew_id": crew_id,
        "panel": panel,
        "biomarker": biomarker,
        "visit": visit,
        "count": len(results),
        "results": [serialize_analysis(result) for result in results],
    }


@router.get("/astronauts/{crew_id}/trajectory")
def crew_trajectory(crew_id: str, panel: Panel, biomarker: str) -> dict[str, Any]:
    """One crew member's postflight trajectory for one biomarker (A3).

    PROVISIONAL until C confirms the shape. The trajectory is A's
    serialize_trajectory() output, unchanged.
    """
    data = _loaded()
    _check_crew(data, crew_id)
    _select_biomarkers(data, panel, biomarker)
    trajectory = data.trajectories.get((crew_id, panel, biomarker))
    if trajectory is None:
        raise HTTPException(
            status_code=404,
            detail=f"No postflight trajectory for {crew_id} in {panel}/{biomarker}",
        )
    return {
        **_envelope(),
        "classification_note": CLASSIFICATION_NOTE,
        "crew_id": crew_id,
        "panel": panel,
        "biomarker": biomarker,
        "trajectory": serialize_trajectory(trajectory),
    }


@router.get("/astronauts/{crew_id}/passport")
def crew_passport(crew_id: str, visit: str) -> dict[str, Any]:
    """A4 biological passport for one crew member at one postflight visit.

    Returns A's build_biological_passport() output unchanged. It is built
    from the A2 and A3 results cached at startup, so no baseline or
    trajectory is recalculated. In URLs, write '+' as %2B (visit=R%2B45).
    """
    data = _loaded()
    _check_crew(data, crew_id)
    postflight = [v for v in data.crew_visits[crew_id] if v.startswith("R")]
    if visit not in postflight:
        hint = " In URLs, write '+' as %2B (R%2B45)." if " " in visit else ""
        raise HTTPException(
            status_code=404,
            detail=(
                f"No postflight visit {visit!r} for {crew_id}. "
                f"Postflight visits: {', '.join(postflight)}.{hint}"
            ),
        )
    return build_biological_passport(
        (result for series in data.analyses.values() for result in series),
        data.trajectories.values(),
        astronaut_id=crew_id,
        selected_visit=visit,
    )


@router.get("/comparison")
def biomarker_comparison(panel: Panel, biomarker: str) -> dict[str, Any]:
    """All crew members' trajectories for one panel and biomarker (A3).

    PROVISIONAL until C confirms the shape. Built with A's
    compare_astronauts(); each entry is A's serialize_trajectory() output.
    """
    data = _loaded()
    _select_biomarkers(data, panel, biomarker)
    series = data.comparisons.get((panel, biomarker), [])
    return {
        **_envelope(),
        "classification_note": CLASSIFICATION_NOTE,
        "panel": panel,
        "biomarker": biomarker,
        "unit": data.panels[panel]["units"][biomarker],
        "count": len(series),
        "trajectories": [serialize_trajectory(trajectory) for trajectory in series],
    }
