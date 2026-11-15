"""Tests for the Mission Environment radiation endpoints (app/radiation.py).

The CSV is loaded by the application's startup step, so each test uses
`with TestClient(app)`. Tests read the repository's Curiosity RAD CSV through
Iliass Barrou's engine, except where a test points elsewhere on purpose.
"""

import json
import socket

import pytest
from fastapi.testclient import TestClient

from app import radiation
from app.main import app
from engine.radiation_history import (
    DEFAULT_CSV_PATH,
    load_radiation_history,
    may_20_event_summary,
    radiation_timeline,
)

BASE = "/api/environment/radiation"
EVENT = f"{BASE}/events/may-20-2024"
CSV_SHA256 = "d514a88fdc9a539a3b470b57a4d28c95cec6b1494474c696a27d629cda1cdea5"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv(radiation.DATA_ENV_VAR, raising=False)
    with TestClient(app) as test_client:  # runs the startup step
        yield test_client


def get_ok(client, path, **params):
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def floats(value):
    if isinstance(value, float):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from floats(item)
    elif isinstance(value, list):
        for item in value:
            yield from floats(item)


def test_full_timeline_is_the_engine_output_unchanged(client):
    body = get_ok(client, f"{BASE}/timeline")
    expected = radiation_timeline(load_radiation_history(DEFAULT_CSV_PATH))
    assert body == json.loads(json.dumps(expected))
    assert body["observation_count"] == 5971
    assert body["unit"] == "µGy/day" and body["measurement"] == "absorbed_dose_rate"
    first = body["series"][0]["observations"][0]
    assert (first["timestamp_utc"], first["value"]) == ("2024-03-07T00:14:58.000Z", "160.92029")


def test_csv_is_stored_byte_for_byte(client):
    # .gitattributes keeps the original line endings, so the hash is the same everywhere.
    assert get_ok(client, f"{BASE}/timeline")["source"]["csv_sha256"] == CSV_SHA256


def test_date_filter_and_statistics_for_may_20(client):
    body = get_ok(client, f"{BASE}/timeline", start_date="2024-05-20", end_date="2024-05-20",
                  include_statistics="true")
    series = body["series"][0]
    assert series["observation_count"] == 139
    assert series["statistics"]["median"] == "1153.6759"
    assert series["statistics"]["peak"]["value"] == "8377.913"
    assert series["statistics"]["peak"]["timestamp_utc"] == "2024-05-20T06:15:19.000Z"


def test_statistics_are_off_by_default(client):
    body = get_ok(client, f"{BASE}/timeline", start_date="2024-05-20", end_date="2024-05-20")
    assert body["series"][0]["statistics"] is None


def test_may_20_event_matches_the_documented_values(client):
    body = get_ok(client, EVENT)
    assert body == json.loads(json.dumps(may_20_event_summary(load_radiation_history(DEFAULT_CSV_PATH))))
    series = body["series"][0]
    week = series["preceding_week_comparison"]
    assert body["evidence_available"] is True and body["event_date"] == "2024-05-20"
    assert series["statistics"]["peak"]["value"] == "8377.913"
    assert series["statistics"]["median"] == "1153.6759"
    assert (week["start_date"], week["end_date"], week["median"]) == ("2024-05-13", "2024-05-19", "148.34653")
    assert week["event_median_to_prior_median_ratio"].startswith("7.77")
    assert body["source_reference"].startswith("https://science.nasa.gov/")


def test_a_valid_range_without_readings_returns_zero_rows(client):
    body = get_ok(client, f"{BASE}/timeline", start_date="2023-01-01", end_date="2023-01-02")
    assert body["observation_count"] == 0


@pytest.mark.parametrize("params", [
    {"start_date": "2024/05/20"},
    {"end_date": "20-05-2024"},
    {"start_date": "2024-02-30"},
    {"start_date": "2024-05-21", "end_date": "2024-05-20"},
])
def test_invalid_dates_are_422_with_a_message(client, params):
    response = client.get(f"{BASE}/timeline", params=params)
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Invalid date filter:")


@pytest.mark.parametrize("path", [f"{BASE}/timeline", EVENT])
def test_unknown_detector_is_404_listing_valid_detectors(client, path):
    response = client.get(path, params={"detector": "Z"})
    assert response.status_code == 404
    assert "Available detectors: E" in response.json()["detail"]


def test_known_detector_filter_works(client):
    assert get_ok(client, f"{BASE}/timeline", detector="E")["observation_count"] == 5971


def test_responses_are_strict_json_with_decimal_strings(client):
    for path, params in [(f"{BASE}/timeline", {"include_statistics": "true"}), (EVENT, {})]:
        body = get_ok(client, path, **params)
        json.dumps(body, allow_nan=False)
        assert list(floats(body)) == []


def test_csv_is_loaded_once_at_startup(monkeypatch):
    monkeypatch.delenv(radiation.DATA_ENV_VAR, raising=False)
    calls = []
    original = radiation.load_radiation_history
    monkeypatch.setattr(radiation, "load_radiation_history",
                        lambda *a, **k: calls.append(1) or original(*a, **k))
    with TestClient(app) as client:
        for _ in range(3):
            get_ok(client, EVENT)
    assert calls == [1]


def test_missing_csv_gives_503_without_paths_and_other_modes_still_work(monkeypatch, tmp_path):
    monkeypatch.setenv(radiation.DATA_ENV_VAR, str(tmp_path / "nowhere.csv"))
    with TestClient(app) as client:
        for path in (f"{BASE}/timeline", EVENT):
            response = client.get(path)
            assert response.status_code == 503
            assert str(tmp_path) not in response.text and "nowhere" not in response.text
        assert client.get("/health").status_code == 200
        assert client.get("/datasets/osd575/astronauts").status_code == 200
        assert client.get("/api/monitoring/astronauts").status_code == 200


def test_unusable_csv_gives_503(monkeypatch, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("not,the,right,header\n1,2,3,4\n", encoding="utf-8")
    monkeypatch.setenv(radiation.DATA_ENV_VAR, str(bad))
    with TestClient(app) as client:
        response = client.get(f"{BASE}/timeline")
        assert response.status_code == 503
        assert "could not be read" in response.json()["detail"]


def test_loading_and_summaries_work_with_network_blocked(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    # Called directly, not through TestClient: on Windows, asyncio opens a
    # local socket pair for its event loop, which this block would stop.
    monkeypatch.delenv(radiation.DATA_ENV_VAR, raising=False)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    try:
        radiation.load_history()
        history = radiation._state.history
        assert radiation_timeline(history)["observation_count"] == 5971
        assert may_20_event_summary(history)["evidence_available"] is True
    finally:
        radiation.clear_history()
