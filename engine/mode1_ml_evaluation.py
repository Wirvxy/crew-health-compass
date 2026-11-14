"""Chronological synthetic evaluation and local model training command."""

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from engine.mode1_detection import HistoryIndex, assess_observation
from engine.mode1_ingestion import (
    DEFAULT_DATA_PATH,
    EvaluationLabel,
    Observation,
    load_evaluation_labels,
    load_monitoring_data,
    serialize_observation,
)
from engine.mode1_ml import ModelSet, fit_models, save_models, score_observation

# The first 120 mission days contain 100 of the 150 observation days.
DEFAULT_CUTOFF = datetime(2030, 5, 1, tzinfo=timezone.utc)
_APPROACHES = ("m2", "ml", "hybrid")


def _row_id(row: Observation | EvaluationLabel) -> tuple[str, int]:
    return row.source_file, row.source_row


def chronological_split(
    observations: Iterable[Observation], *, cutoff: datetime = DEFAULT_CUTOFF
) -> tuple[list[Observation], list[Observation]]:
    """Validate row identities and split all protocols at the same UTC instant."""
    if cutoff.utcoffset() is None:
        raise ValueError("Split cutoff requires a UTC offset")
    cutoff = cutoff.astimezone(timezone.utc)
    train, holdout = [], []
    identities, slots = set(), set()
    for row in observations:
        if row.timestamp.utcoffset() is None:
            raise ValueError("Observation timestamp requires a UTC offset")
        stamp = row.timestamp.astimezone(timezone.utc)
        slot = row.astronaut_id, row.source_file, row.activity_context, stamp
        if _row_id(row) in identities or slot in slots:
            raise ValueError("Duplicate observation across the chronological split")
        identities.add(_row_id(row))
        slots.add(slot)
        (train if stamp < cutoff else holdout).append(row)
    order = lambda row: (row.timestamp.astimezone(timezone.utc), _row_id(row))
    return sorted(train, key=order), sorted(holdout, key=order)


def _metrics(cases: list[dict], approach: str) -> dict[str, object]:
    actual = Counter(case["severity"] for case in cases)
    alarms = Counter(case["severity"] for case in cases if case[approach] is True)
    detected = alarms["mild"] + alarms["critical"]
    missed = actual["mild"] + actual["critical"] - detected
    false_alarms = alarms["normal"]
    return {
        "evaluated": len(cases), "normal": actual["normal"],
        "mild": actual["mild"], "critical": actual["critical"],
        "detected_mild": alarms["mild"], "detected_critical": alarms["critical"],
        "missed_mild": actual["mild"] - alarms["mild"],
        "missed_critical": actual["critical"] - alarms["critical"],
        "false_alarms": false_alarms, "abstentions": sum(case[approach] is None for case in cases),
        "precision": detected / (detected + false_alarms) if detected + false_alarms else None,
        "recall": detected / (detected + missed) if detected + missed else None,
        "f1": (2 * detected / (2 * detected + missed + false_alarms)
               if detected or missed or false_alarms else None),
    }


def _comparison(cases: list[dict]) -> dict[str, object]:
    return {approach: _metrics(cases, approach) for approach in _APPROACHES}


def evaluate(
    observations: Iterable[Observation],
    labels: Iterable[EvaluationLabel],
    *,
    cutoff: datetime = DEFAULT_CUTOFF,
) -> tuple[ModelSet, dict[str, object]]:
    """Fit on earlier synthetic normals and compare three alarm policies on a shared holdout."""
    train, holdout = chronological_split(observations, cutoff=cutoff)
    label_map = {}
    for label in labels:
        key = _row_id(label)
        if key in label_map or label.expected_scenario_severity not in {"normal", "mild", "critical"}:
            raise ValueError("Duplicate evaluation label or unsupported severity")
        label_map[key] = label
    if label_map.keys() != {_row_id(row) for row in (*train, *holdout)}:
        raise ValueError("Evaluation labels must match the monitoring rows one-to-one")

    normals = [row for row in train if label_map[_row_id(row)].expected_scenario_severity == "normal"]
    fingerprint = hashlib.sha256()
    for row in normals:
        fingerprint.update(json.dumps(serialize_observation(row), sort_keys=True, allow_nan=False).encode())
        fingerprint.update(b"\n")
    models = fit_models(
        normals, cutoff=cutoff, dataset_version=f"iss-synthetic-3000:training-sha256:{fingerprint.hexdigest()}"
    )
    # M2's timestamp gate uses only earlier observations, including previous holdout rows.
    history = HistoryIndex((*train, *holdout))
    full_cases = []
    coverage = Counter()
    unavailable_labels = Counter()
    for row in holdout:
        finding = score_observation(row, models)
        ml = finding["is_anomaly"]
        label = label_map[_row_id(row)]
        coverage[row.activity_context, "held_out"] += 1
        if ml is None:
            unavailable_labels[label.expected_scenario_severity] += 1
        else:
            coverage[row.activity_context, "scored"] += 1
        status = assess_observation(row, history)["overall_status"]
        m2 = None if status == "insufficient_data" else status == "unusual"
        full_cases.append({
            "astronaut": row.astronaut_id, "context": row.activity_context,
            "protocol": row.source_file, "scenario": label.scenario,
            "severity": label.expected_scenario_severity,
            "m2": m2, "ml": ml, "hybrid": True if ml else m2,
        })

    cases = [case for case in full_cases if case["ml"] is not None]
    breakdown = {}
    for field in ("astronaut", "context", "protocol", "scenario"):
        breakdown[field] = {
            name: _comparison([case for case in cases if case[field] == name])
            for name in sorted({case[field] for case in cases})
        }
    return models, {
        "dataset_version": models.dataset_version, "sklearn_version": models.sklearn_version,
        "cutoff": models.cutoff.isoformat(), "earlier_rows": len(train), "earlier_normal_rows": len(normals),
        "fitted_models": len(models.models),
        "fitted_training_rows": sum(models.training_counts[key] for key in models.models),
        "training_counts": [
            {"astronaut": key[0], "protocol": key[1], "context": key[2],
             "rows": count, "fitted": key in models.models}
            for key, count in sorted(models.training_counts.items())
        ],
        "held_out": len(holdout), "scored": len(cases),
        "unscored_labels": dict(sorted(unavailable_labels.items())),
        "coverage_by_context": {
            name: {kind: coverage[name, kind] for kind in ("held_out", "scored")}
            for name in sorted({row.activity_context for row in holdout})
        },
        "metrics": _comparison(cases), "full_holdout_metrics": _comparison(full_cases),
        "breakdown": breakdown,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--model-out", type=Path, help="Optional local skops artifact")
    args = parser.parse_args()
    models, report = evaluate(load_monitoring_data(args.source), load_evaluation_labels(args.source))
    if args.model_out:
        report["model_sha256"] = save_models(models, args.model_out)
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
