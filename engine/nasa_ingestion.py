"""Load the four NASA OSD-575 serum panels for offline health replay."""

import csv
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

STUDY_ID = "OSD-575"
STUDY_URL = "https://osdr.nasa.gov/bio/repo/data/studies/OSD-575"
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "mode2"

Phase = Literal["preflight", "postflight"]
Panel = Literal["cmp", "eve_cardiovascular", "eve_immune", "alamar_immune"]
Group = Literal["metabolic", "cardiovascular", "immune"]
MeasurementStatus = Literal["valid", "missing", "invalid"]
_MISSING_MARKERS = {"", "NA", "N/A"}

_SOURCES: dict[Panel, tuple[Group, str, str]] = {
    "cmp": (
        "metabolic",
        "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
        "Sample Name",
    ),
    "eve_cardiovascular": (
        "cardiovascular",
        "LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv",
        "Sample Name",
    ),
    "eve_immune": (
        "immune",
        "LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv",
        "Sample Name",
    ),
    "alamar_immune": (
        "immune",
        "LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv",
        "Sample ID",
    ),
}
_SAMPLE_ID = re.compile(r"(?P<crew>C[0-9]{3})_serum_(?P<visit>L-[0-9]+|R\+[0-9]+)")
# The transformed CSV headers spell out the units used in the submitted files.
_UNITS = {
    "milligram_per_deciliter": "mg/dL",
    "gram_per_deciliter": "g/dL",
    "millimol_per_liter": "mmol/L",
    "units_per_liter": "U/L",
    "milliliter_per_minute_per_1.73_meter_squared": "mL/min/1.73m2",
    "nanogram_per_milliliter": "ng/ml",
    "picogram_per_milliliter": "pg/ml",
    "npq": "NPQ",
}


@dataclass(frozen=True)
class CsvSource:
    """CSV basename, 1-based ending line, and primary value header."""

    file: str
    row: int
    value_column: str


@dataclass(frozen=True)
class SerumMeasurement:
    """One panel's observation for one serum sample and biomarker.

    Day offsets are relative to launch for preflight and return for postflight.
    """

    crew_id: str
    visit: str
    phase: Phase
    phase_day: int
    source_sample_id: str
    group: Group
    panel: Panel
    biomarker: str
    value: Decimal | None
    unit: str
    lab_ref_min: Decimal | None
    lab_ref_max: Decimal | None
    normalized_percent: Decimal | None
    raw_value: str
    raw_lab_ref_min: str | None
    raw_lab_ref_max: str | None
    raw_normalized_percent: str | None
    source: CsvSource
    provenance: str = "dataset:OSD-575"

    @property
    def value_status(self) -> MeasurementStatus:
        """Classify the primary measurement while keeping the original cell text."""
        if self.value is not None and self.value.is_finite():
            return "valid"
        if self.raw_value.strip().upper() in _MISSING_MARKERS:
            return "missing"
        return "invalid"


def serialize_measurement(measurement: SerumMeasurement) -> dict[str, object]:
    """Return a JSON-ready record with finite decimals as exact strings.

    Unavailable numeric fields are None (JSON null). The primary measurement's
    value_status and raw_value distinguish missing and invalid source cells.
    """
    record = asdict(measurement)
    for name, value in record.items():
        if isinstance(value, Decimal):
            record[name] = str(value) if value.is_finite() else None
    record["value_status"] = measurement.value_status
    return record


@dataclass(frozen=True)
class _BiomarkerColumns:
    name: str
    unit: str
    value: str
    ref_min: str | None = None
    ref_max: str | None = None
    percent: str | None = None


def _parse_number(raw: str | None) -> Decimal | None:
    """Parse a finite decimal. Callers retain the raw cell for classification."""
    if raw is None:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def _biomarker_columns(panel: Panel, fields: list[str]) -> list[_BiomarkerColumns]:
    columns = []
    for field in fields:
        if panel == "cmp":
            name, marker, suffix = field.partition("_value")
            if not marker:
                continue
            unit = _UNITS[suffix.removeprefix("_")] if suffix else "(calc)"
            minimum = f"{name}_range_min{suffix}"
            # NASA omits "range_" from these two upper-limit headers.
            max_field = "max" if name in {"alt", "ast"} else "range_max"
            maximum = f"{name}_{max_field}{suffix}"
            columns.append(_BiomarkerColumns(name, unit, field, minimum, maximum))
        else:
            name, marker, suffix = field.partition("_concentration_")
            if not marker:
                continue
            percent_field = "percent_normalized_value" if panel == "alamar_immune" else "percent"
            columns.append(
                _BiomarkerColumns(name, _UNITS[suffix], field, percent=f"{name}_{percent_field}")
            )

    names = {column.name for column in columns}
    if not columns or len(names) != len(columns):
        raise ValueError("Expected unique biomarker value columns")
    for column in columns:
        for companion in (column.ref_min, column.ref_max, column.percent):
            if companion is not None and companion not in fields:
                raise ValueError(f"Missing companion column {companion!r}")
    return columns


def load_osd575_panel(data_dir: str | Path, panel: Panel) -> list[SerumMeasurement]:
    """Read a transformed panel from a directory containing the OSD-575 CSVs."""
    group, filename, sample_column = _SOURCES[panel]
    path = Path(data_dir) / filename
    measurements = []
    seen_samples: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        fields = reader.fieldnames or []
        if sample_column not in fields or len(fields) != len(set(fields)):
            raise ValueError(f"{path}: missing sample column or duplicate headers")
        try:
            columns = _biomarker_columns(panel, fields)
        except (KeyError, ValueError) as error:
            raise ValueError(f"{path}: invalid biomarker headers ({error})") from error

        for row in reader:
            line = reader.line_num
            if None in row or None in row.values():
                raise ValueError(f"{path}:{line}: row does not match CSV headers")
            sample_id = row[sample_column]
            match = _SAMPLE_ID.fullmatch(sample_id)
            if match is None:
                raise ValueError(f"{path}:{line}: invalid sample ID {sample_id!r}")
            if sample_id in seen_samples:
                raise ValueError(f"{path}:{line}: duplicate sample ID {sample_id!r}")
            seen_samples.add(sample_id)
            crew_id, visit = match.groups()
            phase: Phase = "preflight" if visit.startswith("L") else "postflight"
            phase_day = int(visit[1:])

            for column in columns:
                raw_value = row[column.value]
                raw_min = row[column.ref_min] if column.ref_min else None
                raw_max = row[column.ref_max] if column.ref_max else None
                raw_percent = row[column.percent] if column.percent else None
                measurements.append(
                    SerumMeasurement(
                        crew_id=crew_id,
                        visit=visit,
                        phase=phase,
                        phase_day=phase_day,
                        source_sample_id=sample_id,
                        group=group,
                        panel=panel,
                        biomarker=column.name,
                        value=_parse_number(raw_value),
                        unit=column.unit,
                        lab_ref_min=_parse_number(raw_min),
                        lab_ref_max=_parse_number(raw_max),
                        normalized_percent=_parse_number(raw_percent),
                        raw_value=raw_value,
                        raw_lab_ref_min=raw_min,
                        raw_lab_ref_max=raw_max,
                        raw_normalized_percent=raw_percent,
                        source=CsvSource(filename, line, column.value),
                    )
                )

    if not seen_samples:
        raise ValueError(f"{path}: no sample rows")
    return measurements


def load_osd575(data_dir: str | Path = DEFAULT_DATA_DIR) -> list[SerumMeasurement]:
    """Load all four transformed panels exactly once from local files."""
    return [
        measurement
        for panel in _SOURCES
        for measurement in load_osd575_panel(data_dir, panel)
    ]
