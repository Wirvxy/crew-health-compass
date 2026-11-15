"""Tests for the Mode 1 monitoring endpoints (app/monitoring.py).

The synthetic history is loaded by the application's startup step, so each
test uses `with TestClient(app)`, which runs that step. Tests read Person B's
data/mode1/ files through A's engine, except where a test points the
data somewhere else on purpose. The history ends on 2030-06-29.
"""

import json
import socket
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import monitoring
from app.main import app
from engine.mode1_contracts import CHECK_IN_UNITS, validate_assessment

URL = "/api/monitoring/assess"
JSON = {"content-type": "application/json"}
AFTER_HISTORY = "2030-06-30T13:30:00Z"


def check_in(timestamp=AFTER_HISTORY, heart_rate="67", context="rest", **changes):
    body = {
        "astronaut_id": "commander",
        "timestamp": timestamp,
        "activity_context": context,
        "indicators": {
            "heart_rate": {"value": heart_rate, "unit": "bpm"},
            "respiratory_rate": {"value": "15", "unit": "breaths/min"},
            "systolic_bp": {"value": "100", "unit": "mmHg"},
            "diastolic_bp": {"value": "59", "unit": "mmHg"},
            "mood": "good",
        },
    }
    return {**body, **changes}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv(monitoring.DATA_ENV_VAR, raising=False)
    with TestClient(app) as test_client:  # runs the startup step
        yield test_client


def assess_ok(client, body):
    response = client.post(URL, json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert validate_assessment(result) == result  # A's output contract
    return result


def evidence(result, indicator):
    return next(item for item in result["evidence"] if item["indicator"] == indicator)


def test_normal_check_in_is_compared_with_rest_history_only(client):
    result = assess_ok(client, check_in())
    assert result["overall_status"] == "normal"
    assert result["data_origin"] == "user"
    assert result["body_marker"] is None and result["affected_systems"] == []
    for indicator in ("heart_rate", "systolic_bp", "diastolic_bp"):
        stats = evidence(result, indicator)["statistics"]
        assert stats["status"] == "normal"
        assert stats["observation_count"] == 14  # A's default window
        assert stats["history_origins"] == ["synthetic"]
    # Rest history has no breathing rate, so it is reported, not compared.
    assert any(r.startswith("respiratory_rate: no comparable") for r in result["insufficient_data"])
    assert result["next_action_protocol_id"] is None


def test_unusual_heart_rate_gives_cardiovascular_chest_marker(client):
    result = assess_ok(client, check_in(heart_rate="85"))
    assert result["overall_status"] == "unusual"
    assert result["affected_systems"] == ["cardiovascular"]
    assert result["body_marker"] == "chest"
    assert evidence(result, "heart_rate")["statistics"]["anomaly"] is True
    assert "higher than the personal median" in result["statistical_findings"][0]


def test_too_little_earlier_history_is_insufficient_data(client):
    result = assess_ok(client, check_in(timestamp="2030-01-03T13:30:00Z"))
    assert result["overall_status"] == "insufficient_data"
    assert "heart_rate: 3 comparable readings available, 7 required." in result["insufficient_data"]


def test_only_strictly_earlier_readings_are_used(client):
    # A rest reading exists at exactly 13:00 on this day: it must not count.
    at = assess_ok(client, check_in(timestamp="2030-01-07T13:00:00Z"))
    after = assess_ok(client, check_in(timestamp="2030-01-07T13:00:01Z"))
    count = lambda r: evidence(r, "heart_rate")["statistics"]["observation_count"]  # noqa: E731
    assert count(after) == count(at) + 1


def test_rest_and_exercise_histories_are_never_mixed(client):
    rest = evidence(assess_ok(client, check_in(context="rest")), "heart_rate")
    exercise = evidence(assess_ok(client, check_in(context="exercise")), "heart_rate")
    assert float(exercise["baseline"]) > float(rest["baseline"]) + 50


def test_context_other_has_no_comparison(client):
    result = assess_ok(client, check_in(context="other"))
    assert result["overall_status"] == "insufficient_data"
    assert all("no comparable historical measurement protocol" in r or r.startswith("mood:")
               for r in result["insufficient_data"])


@pytest.mark.parametrize("changes", [
    {"activity_context": "sleeping"},
    {"timestamp": "2030-06-30T13:30:00"},  # no UTC offset
    {"data_origin": "simulated"},
    {"astronaut_id": ""},
    {"extra": "field"},
    {"indicators": {"heart_rate": {"value": "67", "unit": "bpm"}}},  # missing indicators
])
def test_invalid_check_ins_are_422_with_a_message(client, changes):
    response = client.post(URL, json=check_in(**changes))
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Invalid check-in:")


@pytest.mark.parametrize("value, unit", [("-5", "bpm"), ("fast", "bpm"), ("67", "beats/min")])
def test_invalid_measurement_values_and_units_are_422(client, value, unit):
    body = check_in()
    body["indicators"]["heart_rate"] = {"value": value, "unit": unit}
    response = client.post(URL, json=body)
    assert response.status_code == 422
    # A's validator names the field for a wrong unit, but not for a bad value.
    assert response.json()["detail"].startswith("Invalid check-in:")


@pytest.mark.parametrize("content", [b"not json", b"[1, 2]", b"\xff\xfe"])
def test_bodies_that_are_not_a_json_object_are_422(client, content):
    response = client.post(URL, content=content, headers={"content-type": "application/json"})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_unknown_astronaut_is_422_and_lists_known_ids(client):
    response = client.post(URL, json=check_in(astronaut_id="C001"))
    assert response.status_code == 422
    assert "commander" in response.json()["detail"]


def test_numbers_keep_their_exact_digits(client):
    text = json.dumps(check_in(heart_rate="67.0")).replace('"100"', "100.50")
    response = client.post(URL, content=text, headers={"content-type": "application/json"})
    result = response.json()
    assert evidence(result, "heart_rate")["value"] == "67.0"
    assert evidence(result, "systolic_bp")["value"] == "100.50"


@pytest.mark.parametrize("content_type", [
    None, "text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x",
])
def test_bodies_not_sent_as_json_are_415(client, content_type):
    # Browsers send these types from other websites without a CORS preflight.
    headers = {"content-type": content_type} if content_type else {}
    response = client.post(URL, content=json.dumps(check_in()), headers=headers)
    assert response.status_code == 415
    assert "application/json" in response.json()["detail"]


def test_json_with_a_charset_is_accepted(client):
    headers = {"content-type": "Application/JSON; charset=utf-8"}
    response = client.post(URL, content=json.dumps(check_in()), headers=headers)
    assert response.status_code == 200, response.text


def test_deeply_nested_json_is_422_not_500(client):
    # Whether this depth overflows the parser depends on the platform's stack
    # (it does on Windows, not on Linux with Python 3.14). Either way: 422.
    depth = 100_000
    response = client.post(URL, content="[" * depth + "]" * depth, headers=JSON)
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Invalid check-in:")


def test_parser_recursion_error_is_422(client, monkeypatch):
    # Force the overflow on every platform. Only monitoring's own json is replaced.
    def overflow(*args, **kwargs):
        raise RecursionError("maximum recursion depth exceeded")
    monkeypatch.setattr(monitoring, "json", SimpleNamespace(loads=overflow))
    response = client.post(URL, json=check_in())
    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid check-in: the JSON is nested too deeply."


def with_reading(indicator, value):
    body = check_in()
    body["indicators"][indicator] = {"value": value, "unit": CHECK_IN_UNITS[indicator]}
    return body


@pytest.mark.parametrize("indicator, value, reason", [
    ("heart_rate", "1e3", "plain number"),  # exponent form
    ("heart_rate", "+72", "plain number"),
    ("heart_rate", ".5", "plain number"),
    ("heart_rate", "77777", "plain number"),  # 5 digits before the point
    ("heart_rate", "72.1234", "plain number"),  # 4 digits after the point
    ("sleep_duration", "7" * 5000, "plain number"),
    ("heart_rate", "0", "heart_rate: a measured value must be above 0"),
    ("respiratory_rate", "0.000", "respiratory_rate: a measured value must be above 0"),
    ("diastolic_bp", "0", "diastolic_bp: a measured value must be above 0"),
    ("diastolic_bp", "100", "systolic_bp must be greater than diastolic_bp"),  # equal
    ("systolic_bp", "50", "systolic_bp must be greater than diastolic_bp"),
    ("sleep_duration", "24.001", "cannot report more than 24 hours"),
])
def test_readings_that_cannot_be_real_are_422(client, indicator, value, reason):
    response = client.post(URL, json=with_reading(indicator, value))
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail.startswith("Invalid check-in:") and reason in detail


def test_json_numbers_in_exponent_form_are_422(client):
    # The JSON number 1e2 is read as Decimal("1E+2"), which would be shown as "1E+2".
    text = json.dumps(check_in()).replace('"67"', "1e2")
    response = client.post(URL, content=text, headers=JSON)
    assert response.status_code == 422
    assert "heart_rate: write the value as a plain number" in response.json()["detail"]


@pytest.mark.parametrize("indicator, value", [
    ("sleep_duration", "0"), ("sleep_duration", "24"), ("heart_rate", "72.125"), ("heart_rate", "1000.5"),
])
def test_values_at_the_format_and_logic_edges_are_assessed(client, indicator, value):
    assess_ok(client, with_reading(indicator, value))


@pytest.mark.parametrize("value", ["300", "0.001"])
def test_no_medical_range_is_applied_yet(client, value):
    # Physiological ranges need a cited source (catalogue/indicators.yaml) and
    # are still open, so these are compared with personal history, not refused.
    result = assess_ok(client, with_reading("heart_rate", value))
    assert result["overall_status"] == "unusual"


def test_m3_isolation_forest_is_not_used(client):
    result = assess_ok(client, check_in(heart_rate="85"))
    assert result["optional_ml_findings"] is None
    assert "engine.mode1_ml" not in sys.modules
    assert "sklearn" not in sys.modules


def test_astronauts_endpoint_lists_roles_contexts_and_time_ranges(client):
    body = client.get("/api/monitoring/astronauts").json()
    assert body["data_origin"] == "synthetic" and body["provenance"] == "simulated"
    assert [a["astronaut_id"] for a in body["astronauts"]] == [
        "commander", "flight_engineer_1", "flight_engineer_2", "flight_engineer_3"]
    assert "other" in body["manual_contexts"]
    for astronaut in body["astronauts"]:
        assert {h["activity_context"] for h in astronaut["history"]} == {
            "rest", "exercise", "recovery", "morning_check", "inflight_vitals_check"}
        assert all(h["observations"] == 150 and h["last"].startswith("2030-06-29")
                   for h in astronaut["history"])


def test_history_is_loaded_once_at_startup(monkeypatch):
    monkeypatch.delenv(monitoring.DATA_ENV_VAR, raising=False)
    calls = []
    original = monitoring.load_monitoring_data
    monkeypatch.setattr(monitoring, "load_monitoring_data",
                        lambda *a, **k: calls.append(1) or original(*a, **k))
    with TestClient(app) as client:
        for _ in range(3):
            assess_ok(client, check_in())
    assert calls == [1]


def test_missing_history_gives_503_without_paths(monkeypatch, tmp_path):
    missing = tmp_path / "nowhere"
    monkeypatch.setenv(monitoring.DATA_ENV_VAR, str(missing))
    with TestClient(app) as client:
        response = client.post(URL, json=check_in())
        assert response.status_code == 503
        assert str(tmp_path) not in response.text and "nowhere" not in response.text
        assert client.get("/health").status_code == 200
        assert client.get("/datasets/osd575/astronauts").status_code == 200


def test_loading_and_assessment_work_with_network_blocked(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    # Called directly, not through TestClient: on Windows, asyncio opens a
    # local socket pair for its event loop, which this block would stop.
    monkeypatch.delenv(monitoring.DATA_ENV_VAR, raising=False)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    try:
        monitoring.load_history()
        result = monitoring.assess_check_in(check_in(heart_rate="85"), monitoring._state.history)
    finally:
        monitoring.clear_history()
    assert result["overall_status"] == "unusual"
