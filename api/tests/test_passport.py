"""Tests for the A4 biological passport endpoint (app/osd575.py).

The OSD-575 dataset is loaded by the application's startup step, so each
test uses `with TestClient(app)`. The expected C002 R+45 response is A's own
example file, generated from the NASA files.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import osd575
from app.main import app

EXAMPLE = Path(__file__).resolve().parents[2] / "engine" / "biological_passport_examples" / "c002_r45.json"
URL = "/datasets/osd575/astronauts/{}/passport"
POSTFLIGHT = ["R+1", "R+45", "R+82", "R+194"]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv(osd575.DATA_DIR_ENV_VAR, raising=False)
    with TestClient(app) as test_client:  # runs the startup step
        yield test_client


def passport(client, crew, visit):
    response = client.get(URL.format(crew), params={"visit": visit})  # sends + as %2B
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


def test_c002_r45_is_a_s_example_unchanged(client):
    expected = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert passport(client, "C002", "R+45") == expected


def test_passport_keeps_nasa_provenance_and_marks_later_observations(client):
    body = passport(client, "C002", "R+45")
    assert body["study_id"] == "OSD-575"
    assert body["data_origin"] == "real_nasa_research"
    assert body["source_references"]
    assert body["trajectories"]["includes_later_observations"] is True
    assert passport(client, "C002", "R+194")["trajectories"]["includes_later_observations"] is False


def test_passport_uses_cached_results_without_recalculating(client, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("A2 or A3 recalculated during a request")

    monkeypatch.setattr(osd575, "analyze_postflight", fail)
    monkeypatch.setattr(osd575, "analyze_trajectories", fail)
    passport(client, "C001", "R+1")


@pytest.mark.parametrize("crew", ["C001", "C002", "C003", "C004"])
def test_every_postflight_visit_is_strict_json_with_decimal_strings(client, crew):
    for visit in POSTFLIGHT:
        body = passport(client, crew, visit)
        assert body["astronaut_id"] == crew and body["selected_visit"] == visit
        json.dumps(body, allow_nan=False)
        assert list(floats(body)) == []  # decimals are strings, not floats


def test_unencoded_plus_gets_a_hint(client):
    response = client.get(URL.format("C002") + "?visit=R+45")  # '+' arrives as a space
    assert response.status_code == 404
    assert "%2B" in response.json()["detail"]


@pytest.mark.parametrize("visit", ["L-44", "R+2", "R45", ""])
def test_preflight_or_unknown_visit_is_404_listing_valid_visits(client, visit):
    response = client.get(URL.format("C002"), params={"visit": visit})
    assert response.status_code == 404
    assert "R+1, R+45, R+82, R+194" in response.json()["detail"]


def test_unknown_crew_is_404(client):
    response = client.get(URL.format("C009"), params={"visit": "R+45"})
    assert response.status_code == 404


def test_missing_visit_is_422(client):
    assert client.get(URL.format("C002")).status_code == 422
