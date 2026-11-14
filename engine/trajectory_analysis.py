"""Describe trajectories across observed OSD-575 postflight visits."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, fields
from decimal import Context, Decimal, localcontext
from typing import Literal

from engine.biomarker_analysis import (
    BaselineStatus,
    BiomarkerAnalysis,
    ChangeDirection,
    IntervalCoverage,
    LabComparison,
    SeriesKey,
)
from engine.nasa_ingestion import CsvSource, Group, MeasurementStatus, Panel

OSD575_POSTFLIGHT_DAYS = (1, 45, 82, 194)
Position = Literal["above", "below", "equal"]
DistanceMovement = Literal["closer", "farther", "unchanged"]
Classification = Literal[
    "consistently_closer", "consistently_farther", "mixed", "unchanged_distance", "insufficient_data"
]


@dataclass(frozen=True)
class TrajectoryVisit:
    visit: str
    phase_day: int
    value: Decimal | None
    value_status: MeasurementStatus
    change_from_baseline: Decimal | None
    distance_from_baseline: Decimal | None
    position_relative_to_baseline: Position | None
    change_direction: ChangeDirection
    distance_movement: DistanceMovement | None
    previous_valid_phase_day: int | None
    days_since_previous_valid: int | None
    lab_comparison: LabComparison
    interval_coverage: IntervalCoverage
    lab_ref_min: Decimal | None
    lab_ref_max: Decimal | None
    source_sample_id: str
    source: CsvSource


@dataclass(frozen=True)
class BiomarkerTrajectory:
    crew_id: str
    panel: Panel
    group: Group
    biomarker: str
    unit: str
    baseline_value: Decimal | None
    baseline_status: BaselineStatus
    baseline_sample_count: int
    valid_preflight_sample_ids: tuple[str, ...]
    visits: tuple[TrajectoryVisit, ...]
    first_observation: TrajectoryVisit | None
    last_observation: TrajectoryVisit | None
    trajectory_classification: Classification
    first_to_last_distance_change: Decimal | None
    crossed_baseline: bool | None
    measurement_direction_reversed: bool | None
    valid_observation_count: int
    missing_observation_count: int
    invalid_observation_count: int
    absent_visit_days: tuple[int, ...]
    evidence_limitations: tuple[str, ...]
    finding: str
    study_id: str
    provenance: str


def _classify(movements: set[DistanceMovement]) -> tuple[Classification, str]:
    if not movements:
        return "insufficient_data", "Insufficient observations or baseline for longitudinal comparison."
    if movements == {"closer"}:
        return "consistently_closer", "Closer to the preflight baseline at each observed step."
    if movements == {"farther"}:
        return "consistently_farther", "Farther from the preflight baseline at each observed step."
    if movements == {"unchanged"}:
        return "unchanged_distance", "Distance from the preflight baseline stayed the same."
    if {"closer", "farther"} <= movements:
        return "mixed", "Movement toward or away from the preflight baseline changed direction."
    return "mixed", "Distance from the preflight baseline changed on some steps and stayed the same on others."


def _make_visit(row: BiomarkerAnalysis, previous: TrajectoryVisit | None) -> TrajectoryVisit:
    value = row.current_value
    if row.current_value_status != "valid" or value is None or not value.is_finite():
        value = None
    change = row.absolute_change if value is not None and row.baseline_status == "complete" else None
    position: Position | None = None
    distance = None
    if change is not None:
        distance = change.copy_abs()
        position = "above" if change > 0 else "below" if change < 0 else "equal"

    movement: DistanceMovement | None = None
    direction: ChangeDirection = "unavailable"
    previous_day = None
    if previous is not None and value is not None:
        previous_day = previous.phase_day
        if distance is not None and previous.distance_from_baseline is not None:
            prior_distance = previous.distance_from_baseline
            movement = "unchanged"
            if distance < prior_distance:
                movement = "closer"
            elif distance > prior_distance:
                movement = "farther"
            if previous.value is not None:
                direction = "unchanged"
                if value > previous.value:
                    direction = "increase"
                elif value < previous.value:
                    direction = "decrease"

    return TrajectoryVisit(
        visit=row.visit,
        phase_day=row.phase_day,
        value=value,
        value_status=row.current_value_status,
        change_from_baseline=change,
        distance_from_baseline=distance,
        position_relative_to_baseline=position,
        change_direction=direction,
        distance_movement=movement,
        previous_valid_phase_day=previous_day,
        days_since_previous_valid=row.phase_day - previous_day if previous_day is not None else None,
        lab_comparison=row.lab_comparison,
        interval_coverage=row.interval_coverage,
        lab_ref_min=row.lab_ref_min,
        lab_ref_max=row.lab_ref_max,
        source_sample_id=row.source_sample_id,
        source=row.source,
    )


def _summarize(rows: list[BiomarkerAnalysis], expected_days: set[int]) -> BiomarkerTrajectory:
    first_row = rows[0]
    series = f"{first_row.crew_id}/{first_row.panel}/{first_row.biomarker}"
    days = {row.phase_day for row in rows}
    if len(days) != len(rows):
        raise ValueError(f"Duplicate postflight day for {series}")
    if len({row.unit for row in rows}) > 1:
        raise ValueError(f"Incompatible units for {series}")
    baselines = {
        (row.baseline_status, row.baseline_value, row.baseline_sample_count, row.valid_preflight_sample_ids)
        for row in rows
    }
    if len(baselines) > 1:
        raise ValueError(f"Inconsistent A2 baseline for {series}")
    if len({(row.group, row.study_id, row.provenance) for row in rows}) > 1:
        raise ValueError(f"Inconsistent provenance for {series}")

    visits: list[TrajectoryVisit] = []
    valid: list[TrajectoryVisit] = []
    for row in rows:
        visit = _make_visit(row, valid[-1] if valid else None)
        visits.append(visit)
        if visit.value is not None:
            valid.append(visit)

    movements = {visit.distance_movement for visit in valid if visit.distance_movement is not None}
    classification, finding = _classify(movements)
    positions = {visit.position_relative_to_baseline for visit in valid}
    crossed = {"above", "below"} <= positions if movements else None
    directions = [visit.change_direction for visit in valid if visit.change_direction != "unavailable"]
    reversed_direction = {"increase", "decrease"} <= set(directions) if len(directions) >= 2 else None
    first = valid[0] if valid else None
    last = valid[-1] if valid else None
    distance_change = None
    if movements and first is not None and last is not None:
        start, end = first.distance_from_baseline, last.distance_from_baseline
        if start is not None and end is not None:
            # Keep all places from both A2-derived distances under any caller context.
            precision = max(start.adjusted(), end.adjusted()) - min(
                start.as_tuple().exponent, end.as_tuple().exponent
            ) + 2
            with localcontext(Context(prec=max(34, precision))):
                distance_change = end - start

    missing = sum(visit.value_status == "missing" for visit in visits)
    invalid = sum(visit.value_status == "invalid" for visit in visits)
    absent_days = tuple(sorted(expected_days - days))
    limitations = []
    if first_row.baseline_status != "complete":
        limitations.append("A complete personal preflight baseline is unavailable.")
    if len(valid) < 2:
        limitations.append("Fewer than two valid postflight observations.")
    elif len(valid) == 2:
        limitations.append("Limited evidence from only two valid postflight observations.")
    if missing or invalid or absent_days:
        limitations.append("The postflight record contains unavailable observations.")

    return BiomarkerTrajectory(
        crew_id=first_row.crew_id,
        panel=first_row.panel,
        group=first_row.group,
        biomarker=first_row.biomarker,
        unit=first_row.unit,
        baseline_value=first_row.baseline_value,
        baseline_status=first_row.baseline_status,
        baseline_sample_count=first_row.baseline_sample_count,
        valid_preflight_sample_ids=first_row.valid_preflight_sample_ids,
        visits=tuple(visits),
        first_observation=first,
        last_observation=last,
        trajectory_classification=classification,
        first_to_last_distance_change=distance_change,
        crossed_baseline=crossed,
        measurement_direction_reversed=reversed_direction,
        valid_observation_count=len(valid),
        missing_observation_count=missing,
        invalid_observation_count=invalid,
        absent_visit_days=absent_days,
        evidence_limitations=tuple(limitations),
        finding=finding,
        study_id=first_row.study_id,
        provenance=first_row.provenance,
    )


def analyze_trajectories(
    comparisons: Iterable[BiomarkerAnalysis],
    *,
    expected_postflight_days: Iterable[int] = OSD575_POSTFLIGHT_DAYS,
) -> list[BiomarkerTrajectory]:
    """Summarize A2 comparisons by crew, panel and biomarker in a stable order."""
    groups: dict[SeriesKey, list[BiomarkerAnalysis]] = defaultdict(list)
    for row in comparisons:
        groups[row.crew_id, row.panel, row.biomarker].append(row)
    expected_days = set(expected_postflight_days)
    return [
        _summarize(sorted(rows, key=lambda row: row.phase_day), expected_days)
        for _, rows in sorted(groups.items())
    ]


def compare_astronauts(
    trajectories: Iterable[BiomarkerTrajectory], *, panel: Panel, biomarker: str
) -> list[BiomarkerTrajectory]:
    """Return chart series for one panel and biomarker in crew ID order."""
    matches = [row for row in trajectories if row.panel == panel and row.biomarker == biomarker]
    if len({row.unit for row in matches}) > 1:
        raise ValueError(f"Incompatible units for {panel}/{biomarker}")
    return sorted(matches, key=lambda row: row.crew_id)


def _serialize_visit(visit: TrajectoryVisit | None) -> dict[str, object] | None:
    if visit is None:
        return None
    payload = asdict(visit)
    for name, value in payload.items():
        if isinstance(value, Decimal):
            payload[name] = str(value) if value.is_finite() else None
    return payload


def serialize_trajectory(trajectory: BiomarkerTrajectory) -> dict[str, object]:
    """Serialize for JSON using exact decimal strings and null for unavailable values."""
    payload = {}
    for field in fields(trajectory):
        value = getattr(trajectory, field.name)
        if field.name == "visits":
            value = [_serialize_visit(visit) for visit in value]
        elif isinstance(value, TrajectoryVisit):
            value = _serialize_visit(value)
        elif isinstance(value, Decimal):
            value = str(value) if value.is_finite() else None
        elif isinstance(value, tuple):
            value = list(value)
        payload[field.name] = value
    return payload
