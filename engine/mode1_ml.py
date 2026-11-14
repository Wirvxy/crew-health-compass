"""Optional offline Isolation Forest models for complete synthetic protocols."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from math import isfinite
from pathlib import Path

from engine.mode1_detection import DetectionConfig, HistoryIndex, assess_check_in, assess_observation
from engine.mode1_ingestion import Observation

MODEL_NAME = "IsolationForest"
MODEL_VERSION = "m3-v1"
MIN_TRAINING_SAMPLES = 50
CONTAMINATION = 0.02
_SOYUZ = "apollo_soyuz_inflight_vitals_iss_synthetic.csv"
_SKYLAB = "skylab4_inflight_exercise_iss_synthetic.csv"
_SOYUZ_FEATURES = (
    ("heart_rate_mean_bpm", "bpm"),
    ("heart_rate_peak_bpm", "bpm"),
    ("respiratory_rate_breaths_per_min", "breaths/min"),
)
_SKYLAB_FEATURES = (
    ("heart_rate_mean_bpm", "bpm"),
    ("systolic_bp_mean_mmhg", "mmHg"),
    ("diastolic_bp_mean_mmhg", "mmHg"),
    ("minute_ventilation_mean_l_min_btps", "L/min BTPS"),
    ("oxygen_uptake_mean_l_min_stpd", "L/min STPD"),
    ("carbon_dioxide_output_mean_l_min_stpd", "L/min STPD"),
)
_FEATURES = {
    (_SOYUZ, "inflight_vitals_check"): _SOYUZ_FEATURES,
    **{(_SKYLAB, context): _SKYLAB_FEATURES for context in ("rest", "exercise", "recovery")},
}
ModelKey = tuple[str, str, str]


@dataclass
class ModelSet:
    dataset_version: str
    sklearn_version: str
    cutoff: datetime
    # Store sklearn pipelines with primitive metadata to support skops persistence.
    models: dict[ModelKey, dict]
    training_counts: dict[ModelKey, int]


def _key(row: Observation) -> ModelKey:
    return row.astronaut_id, row.source_file, row.activity_context


def _utc(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("ML timestamps require a UTC offset")
    return value.astimezone(timezone.utc)


def extract_features(row: Observation) -> tuple[float, ...] | None:
    """Return only the ordered numeric fields for the row's protocol and context."""
    schema = _FEATURES.get((row.source_file, row.activity_context))
    if schema is None:
        return None
    readings = {reading.kind: reading for reading in row.readings}
    if len(readings) != len(row.readings):
        return None
    values = []
    for name, unit in schema:
        reading = readings.get(name)
        if reading is None or reading.unit != unit or reading.value_status != "valid":
            return None
        if reading.value is None or not reading.value.is_finite():
            return None
        value = float(reading.value)
        if not isfinite(value):
            return None
        values.append(value)
    return tuple(values)


def fit_models(
    training_normals: Iterable[Observation], *, cutoff: datetime, dataset_version: str
) -> ModelSet:
    """Fit a personal model per compatible stream using only earlier normal training rows."""
    import sklearn
    from sklearn.ensemble import IsolationForest
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    cutoff = _utc(cutoff)
    groups = defaultdict(list)
    source_rows = set()
    slots = set()
    for row in training_normals:
        stamp = _utc(row.timestamp)
        if stamp >= cutoff:
            raise ValueError("Training observation is at or after the split cutoff")
        source_row = row.source_file, row.source_row
        slot = _key(row), stamp
        if source_row in source_rows or slot in slots:
            raise ValueError("Duplicate training observation")
        source_rows.add(source_row)
        slots.add(slot)
        features = extract_features(row)
        if features is not None:
            groups[_key(row)].append((stamp, features))

    models = {}
    counts = {}
    for key, items in sorted(groups.items()):
        counts[key] = len(items)
        if len(items) < MIN_TRAINING_SAMPLES:
            continue
        ordered = sorted(items)
        pipeline = make_pipeline(
            StandardScaler(),
            IsolationForest(
                n_estimators=100, contamination=CONTAMINATION,
                random_state=42, max_samples="auto", n_jobs=1,
            ),
        )
        pipeline.fit([features for _, features in ordered])
        models[key] = {"pipeline": pipeline, "training_end": ordered[-1][0].isoformat()}
    return ModelSet(dataset_version, sklearn.__version__, cutoff, models, counts)


def score_observation(row: Observation, models: ModelSet | None = None) -> dict[str, object]:
    """Score a complete row after the training cutoff, or explain unavailability."""
    schema = _FEATURES.get((row.source_file, row.activity_context), ())
    key = _key(row)
    count = models.training_counts.get(key, 0) if models else 0
    model = models.models.get(key) if models else None
    result = {
        "model_name": MODEL_NAME, "model_version": MODEL_VERSION,
        "dataset_version": models.dataset_version if models else None,
        "activity_context": row.activity_context, "protocol": row.source_file,
        "astronaut_id": row.astronaut_id, "feature_names": [name for name, _ in schema],
        "training_sample_count": count,
        "training_end": model["training_end"] if model else None,
        "model_available": model is not None, "anomaly_score": None, "is_anomaly": None,
        "limitations": ["Experimental score based on fictional training observations."],
    }
    reason = None
    if not schema:
        reason = "Unsupported protocol or activity context."
    elif models is None:
        reason = "No offline model set was supplied."
    elif model is None:
        reason = "Insufficient eligible personal training observations."
    elif _utc(row.timestamp) < models.cutoff:
        reason = "Observation precedes the scoring cutoff."
    else:
        features = extract_features(row)
        if features is None:
            reason = "Required numeric features are missing, invalid, or use incompatible units."
        else:
            try:
                score = -float(model["pipeline"].decision_function([features])[0])
            except ValueError:
                reason = "Features could not be processed by the fitted model."
            else:
                if isfinite(score):
                    result.update(anomaly_score=score, is_anomaly=score > 0)
                else:
                    reason = "The fitted model returned a nonfinite score."
    if reason:
        result["limitations"].append(reason)
    return result


def assess_with_ml(
    row: Observation, history: HistoryIndex, models: ModelSet | None = None
) -> dict[str, object]:
    """Return the primary M2 assessment with the experimental finding alongside it."""
    return {
        "assessment": assess_observation(row, history),
        "ml_finding": score_observation(row, models),
    }


def assess_check_in_with_ml(
    payload: Mapping[str, object], history: HistoryIndex, *, config: DetectionConfig | None = None
) -> dict[str, object]:
    """Return the M2 check-in assessment and explain why ML cannot score the input."""
    assessment = assess_check_in(payload, history, config=config)
    return {
        "assessment": assessment,
        "ml_finding": {
            "model_name": MODEL_NAME, "model_version": MODEL_VERSION, "dataset_version": None,
            "activity_context": assessment["activity_context"], "protocol": None,
            "astronaut_id": assessment["astronaut_id"], "feature_names": [],
            "training_sample_count": 0, "training_end": None,
            "model_available": False, "anomaly_score": None, "is_anomaly": None,
            "limitations": ["Manual check-ins lack a verified acquisition protocol and the full ML feature set."],
        },
    }


def save_models(models: ModelSet, path: str | Path) -> str:
    """Save the fitted scalers and forests and return the artifact's SHA-256."""
    from skops.io import dumps

    payload = dumps({
        "model_version": MODEL_VERSION, "sklearn_version": models.sklearn_version,
        "dataset_version": models.dataset_version, "cutoff": models.cutoff.isoformat(),
        "series": [
            {"key": list(key), "count": count, "model": models.models.get(key),
             "schema": [list(field) for field in _FEATURES[key[1:]]]}
            for key, count in sorted(models.training_counts.items())
        ],
    })
    Path(path).write_bytes(payload)
    return sha256(payload).hexdigest()


def load_models(path: str | Path, *, expected_sha256: str) -> ModelSet:
    """Load an artifact whose digest was recorded from a trusted local training run."""
    payload = Path(path).read_bytes()
    if sha256(payload).hexdigest() != expected_sha256.lower():
        raise ValueError("Model artifact does not match the trusted SHA-256")
    import sklearn
    from skops.io import loads

    # This one internal sklearn type is required by Isolation Forest. Only
    # deserialize it after checking provenance with the caller's known digest.
    artifact = loads(payload, trusted=["sklearn.tree._tree.Tree"])
    if (artifact["model_version"] != MODEL_VERSION
            or artifact["sklearn_version"] != sklearn.__version__):
        raise ValueError("Incompatible model version. Retrain using this environment.")
    models = {}
    counts = {}
    for series in artifact["series"]:
        key = tuple(series["key"])
        schema = [list(field) for field in _FEATURES.get(key[1:], ())]
        if not schema or series["schema"] != schema or key in counts:
            raise ValueError("Incompatible or duplicate model feature schema")
        counts[key] = series["count"]
        if series["model"] is not None:
            models[key] = series["model"]
    return ModelSet(
        artifact["dataset_version"], artifact["sklearn_version"],
        _utc(datetime.fromisoformat(artifact["cutoff"])), models, counts,
    )
