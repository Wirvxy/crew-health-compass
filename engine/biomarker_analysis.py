"""Compare OSD-575 postflight serum measurements with personal baselines."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from decimal import Context, Decimal, localcontext
from typing import Literal

from engine.nasa_ingestion import (
    STUDY_ID,
    CsvSource,
    Group,
    MeasurementStatus,
    Panel,
    SerumMeasurement,
)

SeriesKey = tuple[str, Panel, str]
BaselineStatus = Literal["complete", "insufficient_baseline", "incompatible_units"]
ChangeDirection = Literal["increase", "decrease", "unchanged", "unavailable"]
LabComparison = Literal["below", "within", "above", "unavailable"]
IntervalCoverage = Literal["two_sided", "lower_only", "upper_only", "none", "invalid"]


@dataclass(frozen=True)
class BiomarkerAnalysis:
    crew_id: str
    panel: Panel
    group: Group
    biomarker: str
    visit: str
    phase: Literal["postflight"]
    phase_day: int
    source_sample_id: str
    current_value: Decimal | None
    current_value_status: MeasurementStatus
    raw_current_value: str
    unit: str
    baseline_value: Decimal | None
    baseline_status: BaselineStatus
    baseline_sample_count: int
    valid_preflight_sample_ids: tuple[str, ...]
    missing_preflight_sample_ids: tuple[str, ...]
    invalid_preflight_sample_ids: tuple[str, ...]
    absolute_change: Decimal | None
    percentage_change: Decimal | None
    change_direction: ChangeDirection
    lab_ref_min: Decimal | None
    lab_ref_max: Decimal | None
    raw_lab_ref_min: str | None
    raw_lab_ref_max: str | None
    lab_comparison: LabComparison
    interval_coverage: IntervalCoverage
    source: CsvSource
    study_id: str
    provenance: str
    analysis_notes: tuple[str, ...]


def group_measurements(
    measurements: Iterable[SerumMeasurement],
) -> dict[SeriesKey, list[SerumMeasurement]]:
    """Group records by crew, panel, and biomarker."""
    groups: dict[SeriesKey, list[SerumMeasurement]] = defaultdict(list)
    for row in measurements:
        groups[row.crew_id, row.panel, row.biomarker].append(row)
    return dict(groups)


def _valid_value(row: SerumMeasurement) -> Decimal | None:
    return row.value if row.value_status == "valid" else None


def _malformed_bound(value: Decimal | None, raw: str | None) -> bool:
    if value is not None:
        return not value.is_finite()
    return raw is not None and raw.strip().upper() not in {"", "NA", "N/A"}


def compare_lab_interval(
    row: SerumMeasurement,
) -> tuple[LabComparison, IntervalCoverage]:
    """Evaluate the observation's own limits, including one-sided intervals."""
    lower, upper = row.lab_ref_min, row.lab_ref_max
    if _malformed_bound(lower, row.raw_lab_ref_min) or _malformed_bound(upper, row.raw_lab_ref_max):
        return "unavailable", "invalid"
    if lower is not None and upper is not None:
        if lower > upper:
            return "unavailable", "invalid"
        coverage: IntervalCoverage = "two_sided"
    elif lower is not None:
        coverage = "lower_only"
    elif upper is not None:
        coverage = "upper_only"
    else:
        return "unavailable", "none"

    value = _valid_value(row)
    if value is None:
        return "unavailable", coverage
    if lower is not None and value < lower:
        return "below", coverage
    if upper is not None and value > upper:
        return "above", coverage
    return "within", coverage


def _precision(values: list[Decimal]) -> int:
    nonzero = [value for value in values if not value.is_zero()]
    if not nonzero:
        return 34
    span = max(value.adjusted() for value in nonzero) - min(
        value.as_tuple().exponent for value in nonzero
    )
    # Leave room for exact sums and differences before dividing for recurring decimals.
    return max(34, span + 1 + 2 * len(str(len(values))))


def analyze_postflight(
    measurements: Iterable[SerumMeasurement], *, min_preflight: int = 3
) -> list[BiomarkerAnalysis]:
    """Return one result per postflight observation in series and visit order.

    The default minimum is three valid preflight samples in the current unit.
    Computed values use a local Decimal context with at least 34 significant
    digits for divisions. The caller controls presentation rounding.
    """
    if isinstance(min_preflight, bool) or not isinstance(min_preflight, int) or min_preflight < 1:
        raise ValueError("min_preflight must be a positive integer")

    results = []
    for key, rows in sorted(group_measurements(measurements).items()):
        if len({row.source_sample_id for row in rows}) != len(rows):
            raise ValueError(f"Duplicate sample ID in biomarker series {key!r}")
        ordered = sorted(rows, key=lambda row: (row.phase_day, row.source_sample_id))
        preflight = [row for row in ordered if row.phase == "preflight"]
        postflight = [row for row in ordered if row.phase == "postflight"]
        readings = [(row, _valid_value(row)) for row in preflight]
        valid_ids = tuple(row.source_sample_id for row, value in readings if value is not None)
        missing_ids = tuple(row.source_sample_id for row in preflight if row.value_status == "missing")
        invalid_ids = tuple(row.source_sample_id for row in preflight if row.value_status == "invalid")
        baseline_values = [value for _, value in readings if value is not None]
        baseline_units = {row.unit for row, value in readings if value is not None}
        count = len(baseline_values)
        mean = total = None
        if count >= min_preflight and len(baseline_units) == 1:
            with localcontext(Context(prec=_precision(baseline_values))):
                total = sum(baseline_values, Decimal(0))
                mean = total / count

        for row in postflight:
            current = _valid_value(row)
            baseline = absolute = percentage = None
            direction: ChangeDirection = "unavailable"
            notes = []
            if baseline_units - {row.unit}:
                baseline_status: BaselineStatus = "incompatible_units"
                notes.append("Personal change unavailable because preflight and current units differ.")
            elif mean is None or total is None:
                baseline_status = "insufficient_baseline"
                notes.append(f"Personal change requires {min_preflight} valid preflight readings.")
            else:
                baseline_status = "complete"
                baseline = mean
                if current is not None:
                    with localcontext(Context(prec=_precision([*baseline_values, current]))):
                        # Equivalent to subtraction using the exact mean, without
                        # subtracting a baseline already rounded by division.
                        difference = current * count - total
                        absolute = difference / count
                        direction = "unchanged"
                        if difference > 0:
                            direction = "increase"
                        elif difference < 0:
                            direction = "decrease"
                        if total:
                            percentage = difference * 100 / total
                        else:
                            notes.append("Percentage change unavailable because the baseline is zero.")
            if current is None:
                notes.append(f"Current measurement is {row.value_status}.")

            lab_comparison, coverage = compare_lab_interval(row)
            if coverage == "lower_only":
                notes.append("Only the lower laboratory reference limit is available.")
            elif coverage == "upper_only":
                notes.append("Only the upper laboratory reference limit is available.")
            elif coverage == "invalid":
                notes.append("Laboratory reference limits are malformed or reversed.")
            if row.panel != "cmp":
                notes.append("Changes are descriptive on the original assay scale and are specific to this panel.")

            lower, upper = row.lab_ref_min, row.lab_ref_max
            results.append(
                BiomarkerAnalysis(
                    crew_id=row.crew_id,
                    panel=row.panel,
                    group=row.group,
                    biomarker=row.biomarker,
                    visit=row.visit,
                    phase="postflight",
                    phase_day=row.phase_day,
                    source_sample_id=row.source_sample_id,
                    current_value=current,
                    current_value_status=row.value_status,
                    raw_current_value=row.raw_value,
                    unit=row.unit,
                    baseline_value=baseline,
                    baseline_status=baseline_status,
                    baseline_sample_count=count,
                    valid_preflight_sample_ids=valid_ids,
                    missing_preflight_sample_ids=missing_ids,
                    invalid_preflight_sample_ids=invalid_ids,
                    absolute_change=absolute,
                    percentage_change=percentage,
                    change_direction=direction,
                    lab_ref_min=lower if lower is not None and lower.is_finite() else None,
                    lab_ref_max=upper if upper is not None and upper.is_finite() else None,
                    raw_lab_ref_min=row.raw_lab_ref_min,
                    raw_lab_ref_max=row.raw_lab_ref_max,
                    lab_comparison=lab_comparison,
                    interval_coverage=coverage,
                    source=row.source,
                    study_id=STUDY_ID,
                    provenance=row.provenance,
                    analysis_notes=tuple(notes),
                )
            )
    return results


def serialize_analysis(result: BiomarkerAnalysis) -> dict[str, object]:
    """Return a JSON-ready record using the same decimal convention as A1."""
    payload = asdict(result)
    for name, value in payload.items():
        if isinstance(value, Decimal):
            payload[name] = str(value)
        elif isinstance(value, tuple):
            payload[name] = list(value)
    return payload
