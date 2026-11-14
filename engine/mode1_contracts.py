"""Draft JSON contracts for manual check-ins and future Mode 1 assessments."""

import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation

CHECK_IN_UNITS = {
    "heart_rate": "bpm",
    "respiratory_rate": "breaths/min",
    "systolic_bp": "mmHg",
    "diastolic_bp": "mmHg",
    "sleep_duration": "h",
}
CONTEXTS = {
    "rest", "exercise", "recovery", "morning_check", "inflight_vitals_check", "other",
}
MOODS = {"low", "fair", "good", "great"}
STATUSES = {"normal", "unusual", "insufficient_data", "rule_supported_warning"}
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)


def _object(value, required, optional=()):
    if not isinstance(value, Mapping) or not set(required) <= value.keys():
        raise ValueError(f"Expected object with fields {', '.join(sorted(required))}")
    if value.keys() - set(required) - set(optional):
        raise ValueError("Unexpected fields in payload")
    return value


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected a nonempty string")
    return value


def _choice(value, allowed, field):
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{field}: unsupported value")
    return value


def _decimal(value, *, nonnegative=False):
    if type(value) not in (str, int, float, Decimal) or not _NUMBER.fullmatch(str(value)):
        raise ValueError("Expected a finite decimal value")
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("Expected a finite decimal value") from error
    if nonnegative and number < 0:
        raise ValueError("Expected a nonnegative physical quantity")
    return str(number)


def _header(payload):
    astronaut = _text(payload["astronaut_id"])
    stamp = payload["timestamp"]
    if not isinstance(stamp, str) or not _TIMESTAMP.fullmatch(stamp):
        raise ValueError("timestamp: expected ISO 8601 date/time with UTC offset")
    return {
        "astronaut_id": astronaut,
        "timestamp": datetime.fromisoformat(stamp).isoformat(),
        "activity_context": _choice(payload["activity_context"], CONTEXTS, "activity_context"),
    }


def _indicator(kind, value):
    if kind == "mood":
        return _choice(value, MOODS, kind)
    expected_unit = CHECK_IN_UNITS.get(kind)
    value = _object(value, {"value", "unit"})
    if expected_unit is None or value["unit"] != expected_unit:
        raise ValueError(f"{kind}: unexpected indicator or unit")
    return {"value": _decimal(value["value"], nonnegative=True), "unit": expected_unit}


def validate_manual_check_in(payload: Mapping[str, object]) -> dict[str, object]:
    """Validate manual input and return canonical JSON data with user provenance."""
    keys = {"astronaut_id", "timestamp", "activity_context", "indicators"}
    payload = _object(payload, keys, {"data_origin"})
    if payload.get("data_origin", "user") != "user":
        raise ValueError("Manual check-ins use user data_origin")
    required = CHECK_IN_UNITS.keys() - {"sleep_duration"}
    indicators = _object(payload["indicators"], required, {"sleep_duration", "mood"})
    clean = {
        kind: _indicator(kind, value)
        for kind, value in indicators.items()
        if kind in required or value is not None
    }
    return {**_header(payload), "indicators": clean, "data_origin": "user"}


def _list(value, item_validator):
    if not isinstance(value, list):
        raise ValueError("Expected a JSON array")
    return [item_validator(item) for item in value]


def _evidence(item):
    item = _object(item, {"indicator", "value", "unit", "baseline"}, {"statistics", "category"})
    indicator = _text(item["indicator"])
    unit = _text(item["unit"])
    if indicator in CHECK_IN_UNITS and unit != CHECK_IN_UNITS[indicator]:
        raise ValueError(f"{indicator}: unexpected evidence unit")
    result = {
        "indicator": indicator,
        "unit": unit,
        "value": None if item["value"] is None else _decimal(item["value"]),
        "baseline": None if item["baseline"] is None else _decimal(item["baseline"]),
    }
    if "statistics" in item:
        result["statistics"] = _statistics(item["statistics"])
    if "category" in item:
        if indicator != "mood" or unit != "category" or result["value"] is not None or result["baseline"] is not None:
            raise ValueError("category requires mood evidence with null numeric values")
        result["category"] = _choice(item["category"], MOODS, "mood")
    return result


def _statistics(value):
    decimals = {"mad", "absolute_deviation", "robust_z", "history_span_days", "trend_slope_per_day"}
    value = _object(value, decimals | {"status", "anomaly", "observation_count", "history_origins"})
    status = _choice(value["status"], STATUSES - {"rule_supported_warning"}, "statistics.status")
    anomaly = value["anomaly"]
    if anomaly is not {"normal": False, "unusual": True, "insufficient_data": None}[status]:
        raise ValueError("statistics.anomaly must match statistics.status")
    count = value["observation_count"]
    if type(count) is not int or count < 0:
        raise ValueError("statistics.observation_count must be a nonnegative integer")
    return {
        **value,
        **{
            name: None if value[name] is None else _decimal(
                value[name], nonnegative=name in {"mad", "absolute_deviation", "history_span_days"}
            )
            for name in sorted(decimals)
        },
        "history_origins": _list(
            value["history_origins"], lambda origin: _choice(origin, {"synthetic", "user"}, "history origin")
        ),
    }


def validate_assessment(payload: Mapping[str, object]) -> dict[str, object]:
    """Validate the draft result shape without making an assessment decision."""
    keys = {
        "astronaut_id", "timestamp", "activity_context", "overall_status", "affected_systems",
        "body_marker", "evidence", "statistical_findings", "optional_ml_findings", "explanation",
        "next_action_protocol_id", "data_origin", "insufficient_data",
    }
    payload = _object(payload, keys, {"approved_rule_id", "mock"})
    status = _choice(payload["overall_status"], STATUSES, "overall_status")
    origin = _choice(payload["data_origin"], {"user", "synthetic"}, "data_origin")
    protocol = payload["next_action_protocol_id"]
    rule = payload.get("approved_rule_id")
    if status == "rule_supported_warning":
        _text(rule)
        _text(protocol)
    if "mock" in payload and type(payload["mock"]) is not bool:
        raise ValueError("mock must be a boolean")
    insufficient = _list(payload["insufficient_data"], _text)
    if status == "insufficient_data" and not insufficient:
        raise ValueError("insufficient_data status requires at least one reason")
    ml = payload["optional_ml_findings"]
    return {
        **payload,
        **_header(payload),
        "overall_status": status,
        "data_origin": origin,
        "affected_systems": _list(payload["affected_systems"], _text),
        "body_marker": None if payload["body_marker"] is None else _text(payload["body_marker"]),
        "evidence": _list(payload["evidence"], _evidence),
        "statistical_findings": _list(payload["statistical_findings"], _text),
        "optional_ml_findings": None if ml is None else _list(ml, _text),
        "explanation": _text(payload["explanation"]),
        "next_action_protocol_id": None if protocol is None else _text(protocol),
        "approved_rule_id": None if rule is None else _text(rule),
        "insufficient_data": insufficient,
    }
