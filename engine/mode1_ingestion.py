"""Read Person B's synthetic ISS observations from a directory or ZIP."""

import csv
import io
import json
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from engine.nasa_ingestion import MeasurementStatus

DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "iss-synthetic-3000"

# Each column retains its statistic and gas-volume convention in its name or unit.
_FORMATS = {
    "apollo10_heart_rate": {"heart_rate_bpm": "bpm"},
    "apollo_soyuz_inflight_vitals": {
        "heart_rate_mean_bpm": "bpm",
        "heart_rate_peak_bpm": "bpm",
        "respiratory_rate_breaths_per_min": "breaths/min",
    },
    "skylab4_inflight_exercise": {
        "heart_rate_mean_bpm": "bpm",
        "systolic_bp_mean_mmhg": "mmHg",
        "diastolic_bp_mean_mmhg": "mmHg",
        "minute_ventilation_mean_l_min_btps": "L/min BTPS",
        "oxygen_uptake_mean_l_min_stpd": "L/min STPD",
        "carbon_dioxide_output_mean_l_min_stpd": "L/min STPD",
    },
}
_EXERCISE_CONTEXTS = {
    "rest": "rest",
    "level_3_cycle_exercise": "exercise",
    "post_exercise_recovery": "recovery",
}


@dataclass(frozen=True)
class Reading:
    kind: str
    unit: str
    value: Decimal | None
    value_status: MeasurementStatus
    raw_value: str


@dataclass(frozen=True)
class Observation:
    astronaut_id: str
    timestamp: datetime
    mission_day: int
    activity_context: str
    source_context: str | None
    source_file: str
    source_row: int
    readings: tuple[Reading, ...]
    data_origin: str = "synthetic"
    provenance: str = "simulated"


@dataclass(frozen=True)
class EvaluationLabel:
    source_file: str
    source_row: int
    expected_scenario_severity: str
    scenario: str
    source_context: str | None


@contextmanager
def _reader(path: str | Path):
    path = Path(path)
    if path.suffix.lower() != ".zip":
        yield lambda name: (path / name).read_text(encoding="utf-8-sig")
        return
    with ZipFile(path) as archive:
        entries = {}
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            name = PurePosixPath(entry.filename).name
            if name in entries:
                raise ValueError(f"Ambiguous ZIP member {name!r}")
            entries[name] = entry

        def read(name):
            if name not in entries:
                raise FileNotFoundError(f"{path}: missing {name}")
            return archive.read(entries[name]).decode("utf-8-sig")

        yield read


def _reading(kind: str, unit: str, raw: str) -> Reading:
    if raw.strip().upper() in {"", "NA", "N/A"}:
        return Reading(kind, unit, None, "missing", raw)
    try:
        value = Decimal(raw)
    except InvalidOperation:
        value = None
    if value is None or not value.is_finite():
        return Reading(kind, unit, None, "invalid", raw)
    return Reading(kind, unit, value, "valid", raw)


def _role_aliases(profiles: object) -> dict[str, str]:
    if not isinstance(profiles, dict) or profiles.get("data_origin") != "synthetic":
        raise ValueError("crew_profiles.json: expected synthetic profiles")
    crew = profiles.get("crew")
    if not isinstance(crew, list) or not crew:
        raise ValueError("crew_profiles.json: expected a nonempty crew array")
    aliases = {}
    roles = set()
    for profile in crew:
        if not isinstance(profile, dict):
            raise ValueError("crew_profiles.json: expected a crew profile object")
        role, pulse_role = profile.get("role"), profile.get("pulseRole")
        if not all(isinstance(alias, str) and alias.strip() for alias in (role, pulse_role)):
            raise ValueError("crew_profiles.json: expected nonempty role and pulseRole strings")
        if role in roles:
            raise ValueError(f"crew_profiles.json: duplicate crew role {role!r}")
        roles.add(role)
        for alias in (role, pulse_role):
            if aliases.setdefault(alias, role) != role:
                raise ValueError(f"crew_profiles.json: ambiguous crew role {alias!r}")
    return aliases


def _joined_rows(read, stem, aliases):
    filename = f"{stem}_iss_synthetic.csv"
    timeline_file = f"{stem}_timeline.json"
    csv_rows = csv.DictReader(io.StringIO(read(filename), newline=""), strict=True)
    fields = csv_rows.fieldnames or []
    context_column = "mission_event" if stem == "apollo10_heart_rate" else "activity_context"
    required = {"crew_role", context_column, *_FORMATS[stem]}
    if stem == "apollo_soyuz_inflight_vitals":
        required.add("mission_day")
    if not required <= set(fields) or len(fields) != len(set(fields)):
        raise ValueError(f"{filename}: missing or duplicate columns")
    timeline = json.loads(read(timeline_file))
    if (
        not isinstance(timeline, dict)
        or timeline.get("csv") != filename
        or timeline.get("data_origin") != "synthetic"
    ):
        raise ValueError(f"{timeline_file}: unexpected CSV or data origin")

    entries = timeline.get("timeline")
    if not isinstance(entries, list):
        raise ValueError(f"{timeline_file}: expected a timeline array")
    index = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{timeline_file}: expected a timeline entry object")
        key = entry.get("csv_row")
        if type(key) is not int or key < 1 or key in index:
            raise ValueError(f"{timeline_file}: invalid or duplicate csv_row {key!r}")
        index[key] = entry

    seen = set()
    first_date = None
    for number, row in enumerate(csv_rows, 1):
        location = f"{filename} data row {number}"
        entry = index.pop(number, None)
        if entry is None or None in row or None in row.values():
            raise ValueError(f"{location}: missing timeline mapping or incorrect CSV field count")
        try:
            astronaut = aliases[row["crew_role"]]
            if astronaut != aliases[entry["crew_role"]]:
                raise ValueError("crew roles disagree")
            day = entry["mission_day"]
            if type(day) is not int or day < 1 or ("mission_day" in row and int(row["mission_day"]) != day):
                raise ValueError("invalid or conflicting mission day")
            stamp = datetime.fromisoformat(entry["timestamp_utc"])
            if stamp.utcoffset() != timedelta(0):
                raise ValueError("timestamp must be UTC")
            mission_start = stamp.date() - timedelta(days=day - 1)
            if first_date is None:
                first_date = mission_start
            if mission_start != first_date:
                raise ValueError("timestamp and mission day disagree")
            if (astronaut, stamp) in seen:
                raise ValueError("duplicate crew timestamp")
            seen.add((astronaut, stamp))
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise ValueError(f"{location}: {error}") from error
        yield number, row, entry, astronaut, stamp, day, row[context_column]
    if index or not seen:
        raise ValueError(f"{timeline_file}: unmatched csv_row entries or empty CSV")


def load_monitoring_data(source: str | Path = DEFAULT_DATA_PATH) -> list[Observation]:
    """Return chronological observations with a strict allowlist of monitoring fields."""
    records = []
    with _reader(source) as read:
        aliases = _role_aliases(json.loads(read("crew_profiles.json")))
        for stem, columns in _FORMATS.items():
            for number, row, _, astronaut, stamp, day, context in _joined_rows(read, stem, aliases):
                if stem == "apollo10_heart_rate":
                    if context != "Morning health check":
                        raise ValueError(f"{stem} data row {number}: unexpected mission event")
                    activity = "morning_check"
                elif stem == "apollo_soyuz_inflight_vitals":
                    activity = "inflight_vitals_check"
                    context = None  # The source field exactly encodes the planted scenario.
                else:
                    if context not in _EXERCISE_CONTEXTS:
                        raise ValueError(f"{stem} data row {number}: unknown activity context {context!r}")
                    activity = _EXERCISE_CONTEXTS[context]
                records.append(Observation(
                    astronaut, stamp, day, activity, context, f"{stem}_iss_synthetic.csv", number,
                    tuple(_reading(kind, unit, row[kind]) for kind, unit in columns.items()),
                ))
    return sorted(records, key=lambda row: (row.timestamp, row.astronaut_id, row.source_file, row.source_row))


def load_evaluation_labels(source: str | Path = DEFAULT_DATA_PATH) -> list[EvaluationLabel]:
    """Read fixture labels separately, keyed by source filename and one-based data row."""
    labels = []
    with _reader(source) as read:
        aliases = _role_aliases(json.loads(read("crew_profiles.json")))
        for stem in _FORMATS:
            for number, _, entry, _, _, _, context in _joined_rows(read, stem, aliases):
                severity, scenario = entry.get("expected_scenario_severity"), entry.get("scenario")
                if not isinstance(severity, str) or not severity or not isinstance(scenario, str) or not scenario:
                    raise ValueError(f"{stem} timeline csv_row {number}: expected evaluation labels")
                labels.append(EvaluationLabel(f"{stem}_iss_synthetic.csv", number, severity, scenario, context))
    return labels


def select_series(
    observations: Iterable[Observation], *, astronaut_id: str, source_file: str,
    kind: str, activity_context: str
) -> list[tuple[Observation, Reading]]:
    """Select one astronaut, source protocol, measurement type and activity context."""
    pairs = [
        (row, reading)
        for row in observations
        if (row.astronaut_id, row.source_file, row.activity_context)
        == (astronaut_id, source_file, activity_context)
        for reading in row.readings
        if reading.kind == kind
    ]
    return sorted(pairs, key=lambda pair: (pair[0].timestamp, pair[0].source_row))


def serialize_observation(observation: Observation) -> dict[str, object]:
    result = asdict(observation)
    result["timestamp"] = observation.timestamp.isoformat()
    result["readings"] = [
        {**asdict(reading), "value": str(reading.value) if reading.value is not None else None}
        for reading in observation.readings
    ]
    return result
