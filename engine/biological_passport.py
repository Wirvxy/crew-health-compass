"""Build descriptive NASA OSD-575 visit summaries from A2 and A3 results."""

import re
from collections import Counter
from collections.abc import Iterable

from engine.biomarker_analysis import BiomarkerAnalysis, serialize_analysis
from engine.nasa_ingestion import STUDY_ID, STUDY_URL
from engine.trajectory_analysis import BiomarkerTrajectory

_PANEL_ORDER = ("cmp", "eve_cardiovascular", "eve_immune", "alamar_immune")
# Fixed display order for familiar CMP measures, independent of change magnitude.
_CMP_FOCUS = ("glucose", "creatinine", "sodium", "potassium", "albumin")


def _counts(rows: list[BiomarkerAnalysis]) -> dict[str, object]:
    baselines = Counter(row.baseline_status for row in rows)
    values = Counter(row.current_value_status for row in rows)
    comparisons = Counter(row.lab_comparison for row in rows)
    coverage = Counter(row.interval_coverage for row in rows)
    return {
        "total_biomarkers_considered": len(rows),
        "complete_baseline_count": baselines["complete"],
        "insufficient_baseline_count": baselines["insufficient_baseline"],
        "incompatible_units_count": baselines["incompatible_units"],
        "measurement_status_counts": {status: values[status] for status in ("valid", "missing", "invalid")},
        "lab_interval_summary": {
            **{status: comparisons[status] for status in ("below", "within", "above", "unavailable")},
            "coverage": {
                status: coverage[status]
                for status in ("two_sided", "lower_only", "upper_only", "none", "invalid")
            },
        },
    }


def _finding(
    row: BiomarkerAnalysis, trajectory: BiomarkerTrajectory | None
) -> tuple[int, str, str] | None:
    if row.lab_comparison == "below":
        return 0, "outside_lab_interval", "The recorded value was below the supplied lower laboratory limit."
    if row.lab_comparison == "above":
        return 0, "outside_lab_interval", "The recorded value was above the supplied upper laboratory limit."
    if row.current_value_status == "valid":
        if (
            row.panel == "cmp" and row.biomarker in _CMP_FOCUS
            and row.change_direction in {"increase", "decrease"}
        ):
            side = "above" if row.change_direction == "increase" else "below"
            return 1, "personal_baseline_change", f"The recorded value was {side} the personal preflight average."
        if trajectory is not None:
            if trajectory.trajectory_classification in {"consistently_closer", "consistently_farther"}:
                return 2, "longitudinal_pattern", trajectory.finding
            if trajectory.crossed_baseline:
                return 2, "longitudinal_pattern", "The full postflight series recorded values on both sides of the personal preflight average."
    if row.current_value_status != "valid":
        return 3, "data_limitation", f"The current measurement was {row.current_value_status}."
    if row.baseline_status != "complete":
        return 3, "data_limitation", "A comparable personal preflight baseline was unavailable."
    if row.interval_coverage == "invalid":
        return 3, "data_limitation", "The supplied laboratory limits were malformed or reversed."
    return None


def _trajectory_index(
    rows: list[BiomarkerAnalysis], trajectories: Iterable[BiomarkerTrajectory]
) -> dict[tuple[str, str], BiomarkerTrajectory]:
    by_key = {(row.panel, row.biomarker): row for row in rows}
    matched = {}
    seen = set()
    for trajectory in trajectories:
        if trajectory.crew_id != rows[0].crew_id:
            continue
        key = trajectory.panel, trajectory.biomarker
        row = by_key.get(key)
        if row is None:
            continue
        if key in seen:
            raise ValueError(f"Duplicate A3 trajectory for {key}")
        seen.add(key)
        visit = next((point for point in trajectory.visits if point.visit == row.visit), None)
        if visit is None:
            continue
        if (
            (trajectory.study_id, trajectory.provenance, trajectory.unit, trajectory.group)
            != (row.study_id, row.provenance, row.unit, row.group)
            or (trajectory.baseline_status, trajectory.baseline_value, trajectory.valid_preflight_sample_ids)
            != (row.baseline_status, row.baseline_value, row.valid_preflight_sample_ids)
            or (visit.source_sample_id, visit.source, visit.value, visit.value_status)
            != (row.source_sample_id, row.source, row.current_value, row.current_value_status)
        ):
            raise ValueError(f"A3 trajectory and A2 visit disagree for {key}")
        matched[key] = trajectory
    return matched


def build_biological_passport(
    comparisons: Iterable[BiomarkerAnalysis],
    trajectories: Iterable[BiomarkerTrajectory] = (),
    *,
    astronaut_id: str,
    selected_visit: str,
    max_findings: int = 8,
) -> dict[str, object]:
    """Return a JSON-ready snapshot for one OSD-575 astronaut/postflight visit."""
    if not re.fullmatch(r"R\+[0-9]+", selected_visit):
        raise ValueError("selected_visit must be a postflight code such as R+45")
    if type(max_findings) is not int or max_findings < 0:
        raise ValueError("max_findings must be a nonnegative integer")
    rows = sorted(
        (row for row in comparisons if row.crew_id == astronaut_id and row.phase == "postflight"
         and row.visit == selected_visit),
        key=lambda row: (_PANEL_ORDER.index(row.panel), row.biomarker),
    )
    if not rows:
        raise LookupError(f"No OSD-575 results for {astronaut_id} at {selected_visit}")
    if len({(row.panel, row.biomarker) for row in rows}) != len(rows):
        raise ValueError("Duplicate A2 panel and biomarker for the selected visit")
    if any(row.study_id != STUDY_ID or row.provenance != "dataset:OSD-575" for row in rows):
        raise ValueError("The selected rows must be from NASA OSD-575")

    trajectory_index = _trajectory_index(rows, trajectories)
    selected_day = int(selected_visit[2:])
    includes_later_observations = any(
        point.phase_day > selected_day and point.value_status == "valid"
        for trajectory in trajectory_index.values()
        for point in trajectory.visits
    )
    totals = _counts(rows)
    panels = []
    classifications = {}
    candidates = []
    references = {}
    for panel in _PANEL_ORDER:
        members = [row for row in rows if row.panel == panel]
        if not members:
            continue
        panels.append({"panel": panel, "group": members[0].group, **_counts(members)})
        panel_classes = {}
        for row in members:
            key = panel, row.biomarker
            trajectory = trajectory_index.get(key)
            if trajectory is not None:
                panel_classes[row.biomarker] = trajectory.trajectory_classification
            finding = _finding(row, trajectory)
            if finding is not None:
                priority, category, explanation = finding
                focus_order = _CMP_FOCUS.index(row.biomarker) if priority == 1 else 0
                candidates.append((priority, focus_order, row, category, explanation))
            source_key = panel, row.source.file, row.source.row, row.source_sample_id
            references[source_key] = {
                "panel": panel, "file": row.source.file, "row": row.source.row,
                "source_sample_id": row.source_sample_id, "provenance": row.provenance,
            }
        classifications[panel] = panel_classes

    selected = []
    for _, _, row, category, explanation in sorted(candidates, key=lambda item: item[:2])[:max_findings]:
        trajectory = trajectory_index.get((row.panel, row.biomarker))
        selected.append({
            **serialize_analysis(row),
            "category": category,
            "trajectory_classification": trajectory.trajectory_classification if trajectory else None,
            "trajectory_scope": "full_postflight_series" if trajectory else None,
            "explanation": explanation,
        })

    limitations = ["OSD-575 serum measurements were collected at discrete preflight and postflight visits."]
    missing = sum(row.current_value_status != "valid" for row in rows)
    baseline_gaps = sum(row.baseline_status != "complete" for row in rows)
    lab_gaps = sum(row.lab_comparison == "unavailable" for row in rows)
    if missing:
        limitations.append(f"{missing} biomarker records have a missing or invalid value at this visit.")
    if baseline_gaps:
        limitations.append(f"{baseline_gaps} biomarker records lack a comparable personal preflight baseline.")
    if lab_gaps:
        limitations.append(f"{lab_gaps} biomarker records have no available laboratory comparison at this visit.")
    if any(row.interval_coverage in {"lower_only", "upper_only"} for row in rows):
        limitations.append("One-sided laboratory comparisons use the single supplied bound.")
    if len(trajectory_index) < len(rows):
        limitations.append(f"A3 trajectories were unavailable for {len(rows) - len(trajectory_index)} records.")
    if len(panels) < len(_PANEL_ORDER):
        limitations.append("One or more NASA panels have no records in the supplied visit data.")

    return {
        "study_id": STUDY_ID,
        "astronaut_id": astronaut_id,
        "selected_visit": selected_visit,
        "data_origin": "real_nasa_research",
        **totals,
        "panels": panels,
        "selected_findings": selected,
        "trajectories": {
            "scope": "full_postflight_series",
            "label": "Full historical trajectory",
            "includes_later_observations": includes_later_observations,
            "classification_counts": dict(sorted(Counter(
                trajectory.trajectory_classification for trajectory in trajectory_index.values()
            ).items())),
            "panels": classifications,
        },
        "limitations": limitations,
        "source_references": {"study_url": STUDY_URL, "samples": list(references.values())},
    }
