"""Tests for the read-only NASA OSD-575 endpoints (app/osd575.py).

The dataset is loaded by the application's startup step, so each test uses
`with TestClient(app)`, which runs that step. Tests read the real CSV files
in data/mode2/ through A's engine, except where a test points the data folder
somewhere else on purpose.
"""

import json
import logging
import socket
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import osd575
from app.main import app
from engine.biomarker_analysis import analyze_postflight, serialize_analysis
from engine.nasa_ingestion import load_osd575
from engine.trajectory_analysis import (
    analyze_trajectories,
    compare_astronauts,
    serialize_trajectory,
)

BASE = "/datasets/osd575"
# The handoff gives these values rounded to two decimals.
TOLERANCE = Decimal("0.005")
ENVELOPE = {"study_id", "provenance", "note"}
CLASSIFICATIONS = {
    "consistently_closer", "consistently_farther", "mixed",
    "unchanged_distance", "insufficient_data",
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv(osd575.DATA_DIR_ENV_VAR, raising=False)
    with TestClient(app) as test_client:  # runs the startup step
        yield test_client


@pytest.fixture
def count_loads(monkeypatch):
    calls = []
    original = osd575.load_osd575

    def counting_loader(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(osd575, "load_osd575", counting_loader)
    return calls


def get_ok(client, path, **params):
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def by_visit(records):
    return {record["visit"]: record for record in records}


def a_s_trajectories():
    return analyze_trajectories(analyze_postflight(load_osd575()))


def assert_decimal_or_null(value, where):
    assert value is None or Decimal(value).is_finite(), where


# --- A1/A2 endpoints -----------------------------------------------------------


def test_lists_four_astronauts_with_visits_in_time_order(client):
    data = get_ok(client, f"{BASE}/astronauts")

    assert set(data) == ENVELOPE | {"astronauts"}
    assert data["provenance"] == "dataset:OSD-575"
    assert [a["crew_id"] for a in data["astronauts"]] == ["C001", "C002", "C003", "C004"]
    assert data["astronauts"][0]["visits"] == ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]


def test_lists_panels_with_302_biomarkers_and_units(client):
    data = get_ok(client, f"{BASE}/panels")

    panels = {p["panel"]: p for p in data["panels"]}
    assert list(panels) == ["cmp", "eve_cardiovascular", "eve_immune", "alamar_immune"]
    assert sum(len(p["biomarkers"]) for p in data["panels"]) == 302
    assert panels["cmp"]["group"] == "metabolic"
    assert {"biomarker": "glucose", "unit": "mg/dL"} in panels["cmp"]["biomarkers"]
    assert "egf" in {b["biomarker"] for b in panels["eve_immune"]["biomarkers"]}
    assert "egf" in {b["biomarker"] for b in panels["alamar_immune"]["biomarkers"]}


def test_c001_glucose_history_keeps_values_units_and_provenance(client):
    data = get_ok(client, f"{BASE}/astronauts/C001/measurements", panel="cmp", biomarker="glucose")

    records = data["measurements"]
    assert data["count"] == len(records) == 7
    assert [r["visit"] for r in records] == ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]
    visits = by_visit(records)
    for visit, expected in [("L-92", "83"), ("L-44", "80"), ("L-3", "69"), ("R+1", "90")]:
        assert Decimal(visits[visit]["value"]) == Decimal(expected)
    assert {r["unit"] for r in records} == {"mg/dL"}
    assert {r["provenance"] for r in records} == {"dataset:OSD-575"}
    assert visits["R+1"]["source"]["file"] == "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv"
    assert visits["R+1"]["value_status"] == "valid"


def test_c001_glucose_r1_matches_handoff_and_a_s_own_output(client):
    data = get_ok(
        client, f"{BASE}/astronauts/C001/postflight", panel="cmp", biomarker="glucose", visit="R+1"
    )

    assert data["count"] == 1
    result = data["results"][0]
    assert Decimal(result["current_value"]) == Decimal("90")
    assert result["unit"] == "mg/dL"
    assert abs(Decimal(result["baseline_value"]) - Decimal("77.33")) <= TOLERANCE
    assert abs(Decimal(result["absolute_change"]) - Decimal("12.67")) <= TOLERANCE
    assert result["baseline_status"] == "complete"
    assert result["baseline_sample_count"] == 3
    assert result["change_direction"] == "increase"
    assert result["lab_comparison"] == "within"
    assert result["interval_coverage"] == "two_sided"
    assert (result["lab_ref_min"], result["lab_ref_max"]) == ("65", "99")
    assert (result["study_id"], result["provenance"]) == ("OSD-575", "dataset:OSD-575")
    expected = next(
        serialize_analysis(r)
        for r in analyze_postflight(load_osd575())
        if (r.crew_id, r.panel, r.biomarker, r.visit) == ("C001", "cmp", "glucose", "R+1")
    )
    assert result == json.loads(json.dumps(expected))


def test_missing_values_are_null_with_status_and_raw_text(client):
    history = by_visit(
        get_ok(client, f"{BASE}/astronauts/C001/measurements", panel="cmp",
               biomarker="bun_to_creatinine_ratio")["measurements"]
    )
    missing = history["L-44"]
    assert (missing["value"], missing["value_status"], missing["raw_value"]) == (None, "missing", "NA")

    result = get_ok(
        client, f"{BASE}/astronauts/C002/postflight", panel="cmp",
        biomarker="bun_to_creatinine_ratio", visit="R+82",
    )["results"][0]
    assert result["current_value"] is None
    assert result["current_value_status"] == "missing"
    assert result["absolute_change"] is None
    assert result["percentage_change"] is None
    assert result["change_direction"] == "unavailable"


def test_insufficient_baseline_is_reported_not_hidden(client):
    result = get_ok(
        client, f"{BASE}/astronauts/C003/postflight", panel="alamar_immune",
        biomarker="activin_a", visit="R+1",
    )["results"][0]

    assert result["baseline_value"] is None
    assert result["baseline_status"] == "insufficient_baseline"
    assert result["baseline_sample_count"] == 2
    assert (result["lab_comparison"], result["interval_coverage"]) == ("unavailable", "none")
    assert result["unit"] == "NPQ"


@pytest.mark.parametrize("crew_id", ["C009", "abc", "c001", "C0011"])
@pytest.mark.parametrize("endpoint", ["measurements", "postflight", "trajectory"])
def test_unknown_or_malformed_crew_id_is_404(client, crew_id, endpoint):
    response = client.get(
        f"{BASE}/astronauts/{crew_id}/{endpoint}", params={"panel": "cmp", "biomarker": "glucose"}
    )

    assert response.status_code == 404
    assert "Unknown crew ID" in response.json()["detail"]


@pytest.mark.parametrize("path", [
    "/astronauts/C001/postflight", "/astronauts/C001/trajectory", "/comparison",
])
@pytest.mark.parametrize("panel, biomarker", [("cmp", "not_a_marker"), ("cmp", "egf")])
def test_unknown_biomarker_in_panel_is_404(client, path, panel, biomarker):
    response = client.get(f"{BASE}{path}", params={"panel": panel, "biomarker": biomarker})

    assert response.status_code == 404
    assert response.json()["detail"] == f"Unknown biomarker '{biomarker}' in panel '{panel}'"


@pytest.mark.parametrize("path", [
    "/astronauts/C001/measurements", "/astronauts/C001/trajectory", "/comparison",
])
def test_unknown_panel_is_422(client, path):
    response = client.get(f"{BASE}{path}", params={"panel": "liver", "biomarker": "glucose"})

    assert response.status_code == 422


def test_visit_without_postflight_result_is_404(client):
    preflight = client.get(
        f"{BASE}/astronauts/C001/postflight",
        params={"panel": "cmp", "biomarker": "glucose", "visit": "L-3"},
    )
    assert preflight.status_code == 404
    assert "R+1, R+45, R+82, R+194" in preflight.json()["detail"]

    unencoded = client.get(f"{BASE}/astronauts/C001/postflight?panel=cmp&visit=R+1")
    assert unencoded.status_code == 404
    assert "%2B" in unencoded.json()["detail"]


def test_every_a1_a2_response_is_strict_json_with_numbers_as_strings_or_null(client):
    numeric = {
        "measurements": ["value", "lab_ref_min", "lab_ref_max", "normalized_percent"],
        "results": ["current_value", "baseline_value", "absolute_change",
                    "percentage_change", "lab_ref_min", "lab_ref_max"],
    }
    for crew in ["C001", "C002", "C003", "C004"]:
        for panel in ["cmp", "eve_cardiovascular", "eve_immune", "alamar_immune"]:
            for endpoint, key in [("measurements", "measurements"), ("postflight", "results")]:
                data = get_ok(client, f"{BASE}/astronauts/{crew}/{endpoint}", panel=panel)
                json.dumps(data, allow_nan=False)  # fails on NaN or Infinity
                assert set(data) - {key, "crew_id", "panel", "biomarker", "visit", "count"} == ENVELOPE
                for record in data[key]:
                    for field in numeric[key]:
                        assert_decimal_or_null(record[field], (crew, panel, field))


# --- A3 trajectory and comparison endpoints ------------------------------------


def test_c001_glucose_trajectory_is_a_s_output_unchanged(client):
    data = get_ok(client, f"{BASE}/astronauts/C001/trajectory", panel="cmp", biomarker="glucose")

    assert set(data) == ENVELOPE | {"classification_note", "crew_id", "panel", "biomarker", "trajectory"}
    assert "not a risk score" in data["classification_note"]
    trajectory = data["trajectory"]
    assert (trajectory["crew_id"], trajectory["unit"]) == ("C001", "mg/dL")
    assert abs(Decimal(trajectory["baseline_value"]) - Decimal("77.33")) <= TOLERANCE
    assert trajectory["baseline_status"] == "complete"
    assert trajectory["trajectory_classification"] == "mixed"
    visits = trajectory["visits"]
    assert [v["visit"] for v in visits] == ["R+1", "R+45", "R+82", "R+194"]
    assert [Decimal(v["value"]) for v in visits] == [90, 84, 91, 87]
    assert [v["position_relative_to_baseline"] for v in visits] == ["above"] * 4
    assert [v["distance_movement"] for v in visits] == [None, "closer", "farther", "closer"]
    assert {v["source"]["file"] for v in visits} == {
        "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv"
    }
    assert (trajectory["study_id"], trajectory["provenance"]) == ("OSD-575", "dataset:OSD-575")
    expected = next(
        serialize_trajectory(t) for t in a_s_trajectories()
        if (t.crew_id, t.panel, t.biomarker) == ("C001", "cmp", "glucose")
    )
    assert trajectory == json.loads(json.dumps(expected))


def test_trajectory_keeps_missing_observations_as_null(client):
    trajectory = get_ok(
        client, f"{BASE}/astronauts/C002/trajectory", panel="cmp", biomarker="bun_to_creatinine_ratio"
    )["trajectory"]

    r82 = by_visit(trajectory["visits"])["R+82"]
    assert (r82["value"], r82["value_status"]) == (None, "missing")
    assert r82["change_from_baseline"] is None
    assert trajectory["missing_observation_count"] >= 1
    assert "unavailable observations" in " ".join(trajectory["evidence_limitations"])


def test_trajectory_with_insufficient_baseline_says_so(client):
    trajectory = get_ok(
        client, f"{BASE}/astronauts/C003/trajectory", panel="alamar_immune", biomarker="activin_a"
    )["trajectory"]

    assert trajectory["trajectory_classification"] == "insufficient_data"
    assert trajectory["baseline_status"] == "insufficient_baseline"
    assert trajectory["baseline_value"] is None
    assert trajectory["baseline_sample_count"] == 2
    assert all(v["distance_from_baseline"] is None for v in trajectory["visits"])


@pytest.mark.parametrize("path", ["/astronauts/C001/trajectory", "/comparison"])
@pytest.mark.parametrize("params", [{"panel": "cmp"}, {"biomarker": "glucose"}, {}])
def test_trajectory_and_comparison_require_panel_and_biomarker(client, path, params):
    assert client.get(f"{BASE}{path}", params=params).status_code == 422


def test_glucose_comparison_covers_four_astronauts_with_their_own_baselines(client):
    data = get_ok(client, f"{BASE}/comparison", panel="cmp", biomarker="glucose")

    assert (data["panel"], data["biomarker"], data["unit"], data["count"]) == ("cmp", "glucose", "mg/dL", 4)
    series = data["trajectories"]
    assert [t["crew_id"] for t in series] == ["C001", "C002", "C003", "C004"]
    for trajectory, baseline in zip(series, ["77.33", "73.00", "71.33", "79.67"], strict=True):
        assert abs(Decimal(trajectory["baseline_value"]) - Decimal(baseline)) <= TOLERANCE
    assert [Decimal(t["first_observation"]["value"]) for t in series] == [90, 83, 103, 97]
    assert {t["provenance"] for t in series} == {"dataset:OSD-575"}
    expected = [
        serialize_trajectory(t)
        for t in compare_astronauts(a_s_trajectories(), panel="cmp", biomarker="glucose")
    ]
    assert series == json.loads(json.dumps(expected))


def test_comparison_uses_panel_to_disambiguate_shared_names(client):
    eve = get_ok(client, f"{BASE}/comparison", panel="eve_immune", biomarker="egf")
    alamar = get_ok(client, f"{BASE}/comparison", panel="alamar_immune", biomarker="egf")

    assert (eve["unit"], alamar["unit"]) == ("pg/ml", "NPQ")
    assert eve["count"] == alamar["count"] == 4
    assert {t["panel"] for t in eve["trajectories"]} == {"eve_immune"}


def test_every_comparison_is_strict_json_with_a_s_classifications_only(client):
    panels = get_ok(client, f"{BASE}/panels")["panels"]
    checked = 0
    for panel in panels:
        for marker in panel["biomarkers"]:
            data = get_ok(client, f"{BASE}/comparison", panel=panel["panel"], biomarker=marker["biomarker"])
            json.dumps(data, allow_nan=False)
            for trajectory in data["trajectories"]:
                assert trajectory["trajectory_classification"] in CLASSIFICATIONS
                assert_decimal_or_null(trajectory["baseline_value"], trajectory["biomarker"])
                assert_decimal_or_null(trajectory["first_to_last_distance_change"], trajectory["biomarker"])
                for visit in trajectory["visits"]:
                    for field in ["value", "change_from_baseline", "distance_from_baseline",
                                  "lab_ref_min", "lab_ref_max"]:
                        assert_decimal_or_null(visit[field], (trajectory["biomarker"], field))
            checked += 1
    assert checked == 302


# --- Startup loading and failure handling ---------------------------------------


def test_dataset_is_loaded_once_at_startup_not_per_request(count_loads, monkeypatch):
    monkeypatch.delenv(osd575.DATA_DIR_ENV_VAR, raising=False)
    with TestClient(app) as client:
        assert len(count_loads) == 1  # loaded before any request
        get_ok(client, f"{BASE}/astronauts")
        get_ok(client, f"{BASE}/astronauts/C002/postflight", panel="eve_immune")
        get_ok(client, f"{BASE}/astronauts/C003/trajectory", panel="cmp", biomarker="glucose")
        get_ok(client, f"{BASE}/comparison", panel="cmp", biomarker="glucose")
    assert len(count_loads) == 1


def test_without_startup_the_endpoints_answer_503_and_do_not_load(count_loads):
    osd575.clear_dataset()
    client = TestClient(app)  # no "with": the startup step does not run

    response = client.get(f"{BASE}/astronauts")

    assert response.status_code == 503
    assert response.json()["detail"] == osd575.NOT_LOADED
    assert count_loads == []


def test_missing_data_gives_clear_503_without_paths_and_is_logged(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv(osd575.DATA_DIR_ENV_VAR, str(tmp_path))
    with caplog.at_level(logging.ERROR, logger="app.osd575"), TestClient(app) as client:
        for path in ["/astronauts", "/comparison?panel=cmp&biomarker=glucose"]:
            response = client.get(f"{BASE}{path}")
            assert response.status_code == 503
            detail = response.json()["detail"]
            assert "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv" in detail
            assert "restart the server" in detail
            assert str(tmp_path) not in detail
        assert client.get("/health").status_code == 200
    assert any("OSD-575 data file missing" in r.getMessage() for r in caplog.records)


def test_unusable_data_gives_503_and_is_logged(monkeypatch, tmp_path, caplog):
    (tmp_path / "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv").write_text(
        "not,the,expected,headers\n1,2,3,4\n", encoding="utf-8"
    )
    monkeypatch.setenv(osd575.DATA_DIR_ENV_VAR, str(tmp_path))
    with caplog.at_level(logging.ERROR, logger="app.osd575"), TestClient(app) as client:
        response = client.get(f"{BASE}/panels")
        assert response.status_code == 503
        assert "could not be read or analysed" in response.json()["detail"]
        assert str(tmp_path) not in response.json()["detail"]
    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_fixing_data_requires_a_restart(monkeypatch, tmp_path):
    monkeypatch.setenv(osd575.DATA_DIR_ENV_VAR, str(tmp_path))
    with TestClient(app) as client:
        assert client.get(f"{BASE}/astronauts").status_code == 503
        monkeypatch.delenv(osd575.DATA_DIR_ENV_VAR)  # data "fixed", no restart
        assert client.get(f"{BASE}/astronauts").status_code == 503
    with TestClient(app) as restarted:
        assert restarted.get(f"{BASE}/astronauts").status_code == 200


def test_loading_and_analysis_work_with_network_blocked(monkeypatch):
    # The network is blocked only around loading and analysis, the code that
    # could otherwise fetch data. The test client itself cannot run under
    # this block: on Windows, asyncio opens a local socket pair for its event
    # loop.
    def no_network(*args, **kwargs):
        raise OSError("network blocked by test")

    monkeypatch.delenv(osd575.DATA_DIR_ENV_VAR, raising=False)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    try:
        osd575.load_dataset()
        state = osd575._state
        assert isinstance(state, osd575.Osd575Data)
        assert sum(len(results) for results in state.analyses.values()) == 4832
        assert len(state.trajectories) == 1208
    finally:
        osd575.clear_dataset()
