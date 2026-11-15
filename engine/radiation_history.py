"""Offline exploration of Curiosity RAD historical absorbed dose rates."""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Context, Decimal, InvalidOperation, localcontext
from hashlib import sha256
from pathlib import Path
from statistics import median
from typing import Literal
from urllib.parse import urlsplit

DATASET_ID = "MSL_RAD_OBS-L2"
DATASET_URL = (
    "https://data.nasa.gov/dataset/"
    "mars-science-laboratory-msl-radiation-assessment-detector-rad-level-2-observation-dosimetr"
)
EVENT_URL = "https://science.nasa.gov/resource/curiosity-sees-streaks-and-specks-during-2024-solar-storm/"
EVENT_DATE = date(2024, 5, 20)
DEFAULT_CSV_PATH = (
    Path(__file__).resolve().parents[1] / "raw data" / "NASA Curiosity radiation"
    / "nasa_curiosity_rad_2024-03-07_to_2024-05-20.csv"
)
_RATE = "absorbed_dose_rate_ugy_per_day"
_HEADERS = {"timestamp_utc", _RATE, "detector", "nasa_cdf_url"}
_UNIT = "µGy/day"
_UTC_STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)")
_DETECTOR = re.compile(r"[A-Z][A-Z0-9_-]*")
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_MISSING = {"", "NA", "N/A"}
_LIMITATIONS = (
    "Sampling intervals vary. Statistics summarize recorded samples with equal weight.",
    "These are detector-specific absorbed dose rates. Accumulated dose and personal exposure require other inputs.",
    "The CSV omits original CDF variable names, quality flags, detector live time, and uncertainties.",
)


@dataclass(frozen=True)
class RadiationObservation:
    timestamp: datetime
    timestamp_utc: str
    detector: str
    value: Decimal | None
    value_status: Literal["valid", "missing", "invalid"]
    raw_value: str
    source_line: int
    nasa_cdf_url: str


@dataclass(frozen=True)
class RadiationHistory:
    source_file: str
    source_sha256: str
    observations: tuple[RadiationObservation, ...]


def _parse_rate(raw_value: str) -> tuple[Decimal | None, Literal["valid", "missing", "invalid"]]:
    value_text = raw_value.strip()
    if value_text.upper() in _MISSING:
        return None, "missing"
    if _NUMBER.fullmatch(value_text):
        try:
            value = Decimal(value_text)
        except InvalidOperation:
            return None, "invalid"
        if value.is_finite() and value >= 0:
            return value, "valid"
    return None, "invalid"


def load_radiation_history(path: str | Path = DEFAULT_CSV_PATH) -> RadiationHistory:
    """Read a local RAD CSV, preserving numeric cell gaps and rejecting structural errors."""
    path = Path(path)
    blob = path.read_bytes()
    reader = csv.DictReader(io.StringIO(blob.decode("utf-8-sig"), newline=""), strict=True)
    observations = []
    seen = set()
    try:
        fields = reader.fieldnames or []
        if len(fields) != len(_HEADERS) or set(fields) != _HEADERS:
            raise ValueError(f"{path}: expected CSV columns {', '.join(sorted(_HEADERS))}")
        for record in reader:
            location = f"{path}:{reader.line_num}"
            if None in record or None in record.values():
                raise ValueError(f"{location}: row does not match CSV headers")
            original_time = record["timestamp_utc"]
            if not _UTC_STAMP.fullmatch(original_time):
                raise ValueError(f"{location}: expected an ISO 8601 UTC timestamp")
            try:
                timestamp = datetime.fromisoformat(original_time)
            except ValueError as error:
                raise ValueError(f"{location}: invalid UTC timestamp") from error
            detector = record["detector"]
            if not _DETECTOR.fullmatch(detector):
                raise ValueError(f"{location}: invalid detector identifier")
            url = record["nasa_cdf_url"]
            source = urlsplit(url)
            if (
                source.scheme != "https" or source.netloc != "cdaweb.gsfc.nasa.gov"
                or not source.path.startswith("/sp_phys/data/msl/rad/cdf/obs-l2/")
                or not source.path.endswith(".cdf")
            ):
                raise ValueError(f"{location}: invalid NASA RAD Level 2 CDF URL")
            key = detector, timestamp
            if key in seen:
                raise ValueError(f"{location}: duplicate observation for {detector} at {original_time}")
            seen.add(key)

            raw_value = record[_RATE]
            value, status = _parse_rate(raw_value)
            observations.append(RadiationObservation(
                timestamp, original_time, detector, value, status, raw_value, reader.line_num, url
            ))
    except csv.Error as error:
        raise ValueError(f"{path}:{reader.line_num}: malformed CSV") from error
    if not observations:
        raise ValueError(f"{path}: no observations")
    observations.sort(key=lambda row: (row.timestamp, row.detector))
    return RadiationHistory(path.name, sha256(blob).hexdigest(), tuple(observations))


def _point(row: RadiationObservation) -> dict[str, object]:
    return {
        "timestamp_utc": row.timestamp_utc, "detector": row.detector,
        "value": str(row.value) if row.value is not None else None,
        "value_status": row.value_status, "raw_value": row.raw_value,
        "source_line": row.source_line, "nasa_cdf_url": row.nasa_cdf_url,
    }


def _metadata(history: RadiationHistory) -> dict[str, object]:
    return {
        "dataset_id": DATASET_ID,
        "data_origin": "historical_nasa_observations",
        "mission": "Mars Science Laboratory (Curiosity)",
        "instrument": "Radiation Assessment Detector (RAD)",
        "measurement": "absorbed_dose_rate",
        "unit": _UNIT,
        "source": {
            "csv_file": history.source_file, "csv_sha256": history.source_sha256,
            "dataset_url": DATASET_URL,
        },
    }


def _group(history: RadiationHistory, detector: str | None) -> dict[str, list[RadiationObservation]]:
    groups: dict[str, list[RadiationObservation]] = {}
    for row in history.observations:
        if detector is None or row.detector == detector:
            groups.setdefault(row.detector, []).append(row)
    if detector is not None and not groups:
        raise ValueError(f"Unknown detector {detector!r}")
    return dict(sorted(groups.items()))


def _date(text: str | None) -> date | None:
    if text is None:
        return None
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
        raise ValueError("Date filter must use YYYY-MM-DD")
    return date.fromisoformat(text)


def _statistics(rows: list[RadiationObservation]) -> dict[str, object]:
    valid = [(row.value, row) for row in rows if row.value is not None]
    counts = {
        "observation_count": len(rows),
        "valid_count": len(valid),
        "missing_count": sum(row.value_status == "missing" for row in rows),
        "invalid_count": sum(row.value_status == "invalid" for row in rows),
    }
    if not valid:
        return {**counts, "min": None, "max": None, "mean": None, "median": None,
                "first_to_last_change": None, "peak": None}
    values = [value for value, _ in valid]
    peak_value, peak_row = max(valid, key=lambda pair: pair[0])
    with localcontext(Context(prec=34)):
        return {
            **counts,
            "min": str(min(values)),
            "max": str(peak_value),
            "mean": str(sum(values, Decimal(0)) / len(values)),
            "median": str(median(values)),
            "first_to_last_change": str(values[-1] - values[0]) if len(valid) > 1 else None,
            "peak": _point(peak_row),
        }


def _series(
    detector: str, rows: list[RadiationObservation], *, include_statistics: bool
) -> dict[str, object]:
    return {
        "detector": detector,
        "start_timestamp_utc": rows[0].timestamp_utc if rows else None,
        "end_timestamp_utc": rows[-1].timestamp_utc if rows else None,
        "observation_count": len(rows),
        "observations": [_point(row) for row in rows],
        "statistics": _statistics(rows) if include_statistics else None,
    }


def radiation_timeline(
    history: RadiationHistory, *, start_date: str | None = None, end_date: str | None = None,
    detector: str | None = None, include_statistics: bool = False,
) -> dict[str, object]:
    """Return chronological observations by detector with inclusive UTC date filters."""
    start, end = _date(start_date), _date(end_date)
    if start is not None and end is not None and start > end:
        raise ValueError("start_date must be on or before end_date")
    series = [
        _series(channel, [
            row for row in rows if (start is None or row.timestamp.date() >= start)
            and (end is None or row.timestamp.date() <= end)
        ], include_statistics=include_statistics)
        for channel, rows in _group(history, detector).items()
    ]
    return {
        **_metadata(history),
        "start_date": start_date,
        "end_date": end_date,
        "observation_count": sum(entry["observation_count"] for entry in series),
        "series": series,
        "limitations": list(_LIMITATIONS),
    }


def _event_comparison(rows: list[RadiationObservation], event_median: str | None) -> dict[str, object]:
    start = EVENT_DATE - timedelta(days=7)
    end = EVENT_DATE - timedelta(days=1)
    prior = [row for row in rows if row.value is not None and start <= row.timestamp.date() <= end]
    observed_dates = len({row.timestamp.date() for row in prior})
    result = {
        "method": "preceding_seven_utc_dates_sample_median",
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "valid_sample_count": len(prior), "observed_date_count": observed_dates,
        "median": None, "event_median_to_prior_median_ratio": None,
    }
    if observed_dates == 7:
        with localcontext(Context(prec=34)):
            reference = median(row.value for row in prior)
            result["median"] = str(reference)
            if event_median is not None and reference > 0:
                result["event_median_to_prior_median_ratio"] = str(Decimal(event_median) / reference)
    return result


def may_20_event_summary(
    history: RadiationHistory, *, detector: str | None = None,
) -> dict[str, object]:
    """Summarize local UTC-day readings for NASA's documented May 20 event."""
    series = []
    for channel, rows in _group(history, detector).items():
        event_rows = [row for row in rows if row.timestamp.date() == EVENT_DATE]
        result = _series(channel, event_rows, include_statistics=True)
        result["preceding_week_comparison"] = _event_comparison(rows, result["statistics"]["median"])
        series.append(result)
    return {
        **_metadata(history),
        "event_date": EVENT_DATE.isoformat(),
        "title": "May 20, 2024 Mars solar radiation event",
        "source_reference": EVENT_URL,
        "description": (
            "NASA reported charged particles arriving at the Martian surface and "
            "a sharp increase recorded by Curiosity RAD on May 20, 2024."
        ),
        "evidence_available": any(entry["statistics"]["valid_count"] for entry in series),
        "series": series,
        "limitations": [
            *_LIMITATIONS,
            "The comparison uses the same detector over the seven preceding UTC dates, "
            "with valid samples required on each date. It describes a local reference period.",
            "The event peak is the highest observed sample on that UTC date. "
            "The extract ends that day, so the later duration of the event is outside its coverage.",
        ],
    }
