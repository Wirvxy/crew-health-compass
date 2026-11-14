"""Personal statistical comparisons for Mode 1."""

from bisect import bisect_left
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Context, Decimal, DecimalException, localcontext
from statistics import median

from engine.mode1_contracts import validate_assessment, validate_manual_check_in
from engine.mode1_ingestion import Observation

_APOLLO = "apollo10_heart_rate_iss_synthetic.csv"
_SOYUZ = "apollo_soyuz_inflight_vitals_iss_synthetic.csv"
_SKYLAB = "skylab4_inflight_exercise_iss_synthetic.csv"
_SKYLAB_READINGS = {
    "heart_rate": (_SKYLAB, "heart_rate_mean_bpm"),
    "systolic_bp": (_SKYLAB, "systolic_bp_mean_mmhg"),
    "diastolic_bp": (_SKYLAB, "diastolic_bp_mean_mmhg"),
}
_MANUAL_PROTOCOLS = {
    "morning_check": {"heart_rate": (_APOLLO, "heart_rate_bpm")},
    "inflight_vitals_check": {
        "heart_rate": (_SOYUZ, "heart_rate_mean_bpm"),
        "respiratory_rate": (_SOYUZ, "respiratory_rate_breaths_per_min"),
    },
    "rest": _SKYLAB_READINGS,
    "exercise": _SKYLAB_READINGS,
    "recovery": _SKYLAB_READINGS,
}
_INDICATORS = {
    "heart_rate_bpm": "heart_rate",
    "heart_rate_mean_bpm": "heart_rate",
    "heart_rate_peak_bpm": "peak_heart_rate",
    "respiratory_rate_breaths_per_min": "respiratory_rate",
    "systolic_bp_mean_mmhg": "systolic_bp",
    "diastolic_bp_mean_mmhg": "diastolic_bp",
    "minute_ventilation_mean_l_min_btps": "minute_ventilation",
}
_SYSTEMS = {
    "heart_rate": "cardiovascular", "peak_heart_rate": "cardiovascular",
    "systolic_bp": "cardiovascular", "diastolic_bp": "cardiovascular",
    "respiratory_rate": "respiratory", "minute_ventilation": "respiratory",
    "sleep_duration": "wellbeing", "mood": "wellbeing",
}
_MARKERS = {"cardiovascular": "chest", "respiratory": "lungs", "wellbeing": "head"}
_Z_SCALE = Decimal("0.6745")
_SECONDS_PER_DAY = Decimal(86400)
_SeriesKey = tuple[str, str, str, str, str]


@dataclass(frozen=True)
class DetectionConfig:
    min_history: int = 7
    window_size: int = 14
    anomaly_threshold: Decimal = Decimal("3.5")
    mad_floor_ratio: Decimal = Decimal("1e-12")
    indicator_systems: Mapping[str, str] = field(default_factory=_SYSTEMS.copy)
    body_markers: Mapping[str, str] = field(default_factory=_MARKERS.copy)

    def __post_init__(self) -> None:
        if type(self.min_history) is not int or type(self.window_size) is not int:
            raise ValueError("history sizes must be integers")
        if not 2 <= self.min_history <= self.window_size:
            raise ValueError("expected 2 <= min_history <= window_size")
        for name in ("anomaly_threshold", "mad_floor_ratio"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise ValueError(f"{name} must be a finite nonnegative Decimal")
        if not self.anomaly_threshold:
            raise ValueError("anomaly_threshold must be positive")


def _utc(timestamp: datetime) -> datetime:
    if timestamp.utcoffset() is None:
        raise ValueError("observation timestamps require a UTC offset")
    return timestamp.astimezone(timezone.utc)


@dataclass(frozen=True)
class _Sample:
    timestamp: datetime
    value: Decimal
    origin: str


class HistoryIndex:
    """Index valid, comparable M1 readings for repeated as-of queries."""

    def __init__(self, observations: Iterable[Observation]) -> None:
        series: dict[_SeriesKey, list[_Sample]] = defaultdict(list)
        for row in observations:
            timestamp = _utc(row.timestamp)
            for reading in row.readings:
                value = reading.value
                if reading.value_status != "valid" or value is None or not value.is_finite():
                    continue
                key = row.astronaut_id, row.activity_context, row.source_file, reading.kind, reading.unit
                series[key].append(_Sample(timestamp, value, row.data_origin))
        self._series = {}
        for key, samples in series.items():
            samples.sort(key=lambda sample: sample.timestamp)
            timestamps = [sample.timestamp for sample in samples]
            if len(set(timestamps)) != len(timestamps):
                raise ValueError(f"duplicate timestamp in historical series {key!r}")
            self._series[key] = timestamps, samples

    def _before(self, key: _SeriesKey, timestamp: datetime, limit: int) -> list[_Sample]:
        timestamps, samples = self._series.get(key, ([], []))
        end = bisect_left(timestamps, timestamp)
        return samples[max(0, end - limit):end]


def _days(start: datetime, end: datetime) -> Decimal:
    elapsed = end - start
    seconds = Decimal(elapsed.days * 86400 + elapsed.seconds)
    return (seconds + Decimal(elapsed.microseconds).scaleb(-6)) / _SECONDS_PER_DAY


def _statistics(value: Decimal | None, samples: list[_Sample], config: DetectionConfig) -> dict:
    status = "insufficient_data"
    anomaly = None
    baseline = mad = deviation = score = span = slope = None
    reason = None
    with localcontext(Context(prec=34)):
        if len(samples) >= 2:
            span = _days(samples[0].timestamp, samples[-1].timestamp)
            slope = median(
                (later.value - earlier.value) / _days(earlier.timestamp, later.timestamp)
                for index, later in enumerate(samples)
                for earlier in samples[:index]
            )
        if len(samples) >= config.min_history:
            values = [sample.value for sample in samples]
            baseline = median(values)
            mad = median(abs(point - baseline) for point in values)
        if value is None:
            reason = "current value unavailable"
        elif baseline is None or mad is None:
            reason = f"{len(samples)} comparable readings available, {config.min_history} required"
        else:
            deviation = abs(value - baseline)
            floor = max(baseline.copy_abs(), Decimal(1)) * config.mad_floor_ratio
            if not mad:
                reason = "historical MAD is zero"
            elif mad < floor:
                reason = "historical MAD is below the numerical stability floor"
            else:
                score = _Z_SCALE * (value - baseline) / mad
                anomaly = abs(score) > config.anomaly_threshold
                status = "unusual" if anomaly else "normal"
    return {
        "baseline": baseline,
        "reason": reason,
        "statistics": {
            "mad": mad, "absolute_deviation": deviation, "robust_z": score,
            "status": status, "anomaly": anomaly, "observation_count": len(samples),
            "history_span_days": span, "trend_slope_per_day": slope,
            "history_origins": sorted({sample.origin for sample in samples}),
        },
    }


def _statistical_evidence(value: Decimal | None, samples: list[_Sample], config: DetectionConfig) -> dict:
    try:
        return _statistics(value, samples, config)
    except DecimalException:
        # The input contract can preserve finite values beyond the working context.
        return {
            "baseline": None,
            "reason": "values exceed the statistical arithmetic range",
            "statistics": {
                "mad": None, "absolute_deviation": None, "robust_z": None,
                "status": "insufficient_data", "anomaly": None, "observation_count": len(samples),
                "history_span_days": None, "trend_slope_per_day": None,
                "history_origins": sorted({sample.origin for sample in samples}),
            },
        }


def _assess(
    astronaut: str, timestamp: datetime, context: str, origin: str,
    inputs: Iterable[tuple[str, str, Decimal | str | None, tuple[str, str] | None]],
    history: HistoryIndex, config: DetectionConfig,
) -> dict[str, object]:
    timestamp = _utc(timestamp)
    evidence = []
    limitations = []
    findings = []
    systems = []
    has_normal = False
    for indicator, unit, current, protocol in inputs:
        value = current if isinstance(current, Decimal) else None
        samples = []
        if protocol is not None:
            source, kind = protocol
            samples = history._before((astronaut, context, source, kind, unit), timestamp, config.window_size)
        result = _statistical_evidence(value, samples, config)
        reason = result.pop("reason")
        if protocol is None:
            reason = ("categorical mood has no numerical baseline" if indicator == "mood"
                      else "no comparable historical measurement protocol for this context")
        stats = result["statistics"]
        item = {"indicator": indicator, "unit": unit, "value": value, **result}
        if isinstance(current, str):
            item["category"] = current
        evidence.append(item)
        if reason is not None:
            limitations.append(f"{indicator}: {reason}.")
        elif stats["anomaly"]:
            direction = "higher" if value > result["baseline"] else "lower"
            findings.append(
                f"{indicator} in {context} is {direction} than the personal median "
                f"({value} vs {result['baseline']} {unit})."
            )
            system = config.indicator_systems.get(indicator)
            if system and system not in systems:
                systems.append(system)
        else:
            has_normal = True
    if findings:
        status = "unusual"
        explanation = " ".join([*findings, "The statistical rule compares readings with personal history."])
    elif has_normal:
        status = "normal"
        explanation = "The supported comparisons did not exceed the statistical threshold."
    else:
        status = "insufficient_data"
        explanation = "Comparable history or historical variability is insufficient for statistical assessment."
        if not limitations:
            limitations.append("No indicators were available to compare.")
    return validate_assessment({
        "astronaut_id": astronaut, "timestamp": timestamp.isoformat(), "activity_context": context,
        "data_origin": origin, "overall_status": status, "affected_systems": systems,
        "body_marker": next((config.body_markers[s] for s in systems if s in config.body_markers), None),
        "evidence": evidence, "statistical_findings": findings, "optional_ml_findings": None,
        "explanation": explanation, "next_action_protocol_id": None, "insufficient_data": limitations,
    })


def assess_check_in(
    payload: Mapping[str, object], history: HistoryIndex, *, config: DetectionConfig | None = None
) -> dict[str, object]:
    """Validate and assess a manual check-in using its matching historical protocol."""
    check_in = validate_manual_check_in(payload)
    context = check_in["activity_context"]
    protocols = _MANUAL_PROTOCOLS.get(context, {})
    inputs = []
    for indicator, raw in sorted(check_in["indicators"].items()):
        if indicator == "mood":
            inputs.append((indicator, "category", raw, None))
        else:
            inputs.append((indicator, raw["unit"], Decimal(raw["value"]), protocols.get(indicator)))
    return _assess(
        check_in["astronaut_id"], datetime.fromisoformat(check_in["timestamp"]), context,
        check_in["data_origin"], inputs, history, config or DetectionConfig(),
    )


def assess_observation(
    observation: Observation, history: HistoryIndex, *, config: DetectionConfig | None = None
) -> dict[str, object]:
    """Replay a synthetic M1 observation with its original protocol and provenance."""
    inputs = [
        (
            _INDICATORS.get(reading.kind, reading.kind), reading.unit,
            reading.value if reading.value_status == "valid" and reading.value is not None
            and reading.value.is_finite() else None,
            (observation.source_file, reading.kind),
        )
        for reading in observation.readings
    ]
    return _assess(
        observation.astronaut_id, observation.timestamp, observation.activity_context,
        observation.data_origin, inputs, history, config or DetectionConfig(),
    )
