"""Read-only endpoints for the NASA OSD-575 serum dataset.

These endpoints only expose Person A's engine (engine/nasa_ingestion.py and
engine/biomarker_analysis.py):
- They load the local CSV files once and run A's analysis.
- They return A's serializer output unchanged.
- No calculation is repeated here, and nothing is downloaded at runtime.

The results are descriptive laboratory comparisons, not clinical alerts,
diagnoses or advice. They are separate from the daily check-in data that the
rest of the API will store.

PROVISIONAL: the response envelopes and error messages are not in the shared
contracts yet (the error format is TBD at G1).
"""

import csv
import logging
import os
import threading
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

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

DATA_DIR_ENV_VAR = "CREW_HEALTH_OSD575_DIR"
PROVENANCE = "dataset:OSD-575"
NOTE = (
    "Descriptive comparison of NASA OSD-575 laboratory data. "
    "Not a clinical assessment, diagnosis or treatment advice."
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/datasets/osd575", tags=["NASA OSD-575 (descriptive)"])

SeriesKey = tuple[str, str, str]  # (crew_id, panel, biomarker)


@dataclass(frozen=True)
class Osd575Data:
    """Lookup tables built once from A's functions."""

    measurements: dict[SeriesKey, list[SerumMeasurement]]
    analyses: dict[SeriesKey, list[BiomarkerAnalysis]]
    crew_visits: dict[str, list[str]]  # crew -> visit codes in time order
    panels: dict[str, dict[str, Any]]  # panel -> {"group": ..., "units": {biomarker: unit}}


_data: Osd575Data | None = None
_lock = threading.Lock()


def data_dir() -> Path:
    """Folder holding the four TRANSFORMED CSVs (default: repository download/)."""
    value = os.environ.get(DATA_DIR_ENV_VAR)
    return Path(value) if value else DEFAULT_DATA_DIR


def _build(directory: Path) -> Osd575Data:
    rows = load_osd575(directory)
    measurements = {
        key: sorted(series, key=lambda row: (row.phase_day, row.source_sample_id))
        for key, series in group_measurements(rows).items()
    }
    analyses: dict[SeriesKey, list[BiomarkerAnalysis]] = defaultdict(list)
    for result in analyze_postflight(rows):
        analyses[result.crew_id, result.panel, result.biomarker].append(result)

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
    return Osd575Data(measurements, dict(analyses), crew_visits, panels)


def get_data() -> Osd575Data:
    """Load and analyse the dataset on first use, then reuse it.

    A failed load is not remembered, so the next request tries again.
    """
    global _data
    if _data is None:
        with _lock:
            if _data is None:
                _data = _build(data_dir())
    return _data


def reset_cache() -> None:
    """Forget the loaded data so the next request reads the files again."""
    global _data
    with _lock:
        _data = None


def _loaded() -> Osd575Data:
    try:
        return get_data()
    except FileNotFoundError as error:
        logger.exception("OSD-575 data file missing")
        name = Path(error.filename).name if error.filename else "a required file"
        raise HTTPException(
            status_code=503,
            detail=(
                f"OSD-575 data file not found: {name}. Put the four OSD-575 "
                f"TRANSFORMED CSV files in the folder set by {DATA_DIR_ENV_VAR} "
                "(default: the repository's download/ folder). Nothing is "
                "downloaded at runtime."
            ),
        ) from None
    except (ValueError, csv.Error, UnicodeDecodeError):
        logger.exception("OSD-575 data files could not be read")
        raise HTTPException(
            status_code=503,
            detail=(
                "OSD-575 data files could not be read. Check that they are the "
                "original NASA TRANSFORMED CSV files."
            ),
        ) from None


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
