"""Tests for the read-only NASA OSD-575 endpoints (app/osd575.py).

They use the real CSV files in download/ through A's engine, except where a
test points the data folder somewhere else on purpose.
"""

import json
import socket
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import osd575
from app.main import app
from engine.biomarker_analysis import analyze_postflight, serialize_analysis
from engine.nasa_ingestion import load_osd575

client = TestClient(app)
BASE = "/datasets/osd575"
# The handoff gives these values rounded to two decimals.
TOLERANCE = Decimal("0.005")
ENVELOPE = {"study_id", "provenance", "note"}


@pytest.fixture(autouse=True)
def fresh_data(monkeypatch):
    monkeypatch.delenv(osd575.DATA_DIR_ENV_VAR, raising=False)
    osd575.reset_cache()
    yield
    osd575.reset_cache()


def get_ok(path, **params):
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def by_visit(records):
    return {record["visit"]: record for record in records}


def test_lists_four_astronauts_with_visits_in_time_order():
    data = get_ok(f"{BASE}/astronauts")

    assert set(data) == ENVELOPE | {"astronauts"}
    assert data["provenance"] == "dataset:OSD-575"
    assert [a["crew_id"] for a in data["astronauts"]] == ["C001", "C002", "C003", "C004"]
    assert data["astronauts"][0]["visits"] == ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]


def test_lists_panels_with_302_biomarkers_and_units():
    data = get_ok(f"{BASE}/panels")

    panels = {p["panel"]: p for p in data["panels"]}
    assert list(panels) == ["cmp", "eve_cardiovascular", "eve_immune", "alamar_immune"]
    assert sum(len(p["biomarkers"]) for p in data["panels"]) == 302
    assert panels["cmp"]["group"] == "metabolic"
    assert {"biomarker": "glucose", "unit": "mg/dL"} in panels["cmp"]["biomarkers"]
    # The same name can appear in two panels, so the panel is always part of the key.
    assert "egf" in {b["biomarker"] for b in panels["eve_immune"]["biomarkers"]}
    assert "egf" in {b["biomarker"] for b in panels["alamar_immune"]["biomarkers"]}


def test_c001_glucose_history_keeps_values_units_and_provenance():
    data = get_ok(f"{BASE}/astronauts/C001/measurements", panel="cmp", biomarker="glucose")

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


def test_c001_glucose_r1_matches_handoff_and_a_s_own_output():
    data = get_ok(
        f"{BASE}/astronauts/C001/postflight", panel="cmp", biomarker="glucose", visit="R+1"
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
    # The API returns A's serializer output unchanged; nothing is recalculated.
    expected = next(
        serialize_analysis(r)
        for r in analyze_postflight(load_osd575())
        if (r.crew_id, r.panel, r.biomarker, r.visit) == ("C001", "cmp", "glucose", "R+1")
    )
    assert result == json.loads(json.dumps(expected))


def test_missing_values_are_null_with_status_and_raw_text():
    history = by_visit(
        get_ok(f"{BASE}/astronauts/C001/measurements", panel="cmp",
               biomarker="bun_to_creatinine_ratio")["measurements"]
    )
    missing = history["L-44"]
    assert (missing["value"], missing["value_status"], missing["raw_value"]) == (None, "missing", "NA")

    result = get_ok(
        f"{BASE}/astronauts/C002/postflight", panel="cmp",
        biomarker="bun_to_creatinine_ratio", visit="R+82",
    )["results"][0]
    assert result["current_value"] is None
    assert result["current_value_status"] == "missing"
    assert result["absolute_change"] is None
    assert result["percentage_change"] is None
    assert result["change_direction"] == "unavailable"


def test_insufficient_baseline_is_reported_not_hidden():
    result = get_ok(
        f"{BASE}/astronauts/C003/postflight", panel="alamar_immune",
        biomarker="activin_a", visit="R+1",
    )["results"][0]

    assert result["baseline_value"] is None
    assert result["baseline_status"] == "insufficient_baseline"
    assert result["baseline_sample_count"] == 2
    assert (result["lab_comparison"], result["interval_coverage"]) == ("unavailable", "none")
    assert result["unit"] == "NPQ"


@pytest.mark.parametrize("crew_id", ["C009", "abc", "c001", "C0011"])
@pytest.mark.parametrize("endpoint", ["measurements", "postflight"])
def test_unknown_or_malformed_crew_id_is_404(crew_id, endpoint):
    response = client.get(f"{BASE}/astronauts/{crew_id}/{endpoint}", params={"panel": "cmp"})

    assert response.status_code == 404
    assert "Unknown crew ID" in response.json()["detail"]


@pytest.mark.parametrize("panel, biomarker", [("cmp", "not_a_marker"), ("cmp", "egf")])
def test_unknown_biomarker_in_panel_is_404(panel, biomarker):
    response = client.get(
        f"{BASE}/astronauts/C001/postflight", params={"panel": panel, "biomarker": biomarker}
    )

    assert response.status_code == 404
    assert f"Unknown biomarker '{biomarker}' in panel '{panel}'" == response.json()["detail"]


def test_unknown_panel_is_422():
    response = client.get(f"{BASE}/astronauts/C001/measurements", params={"panel": "liver"})

    assert response.status_code == 422


def test_visit_without_postflight_result_is_404():
    preflight = client.get(
        f"{BASE}/astronauts/C001/postflight",
        params={"panel": "cmp", "biomarker": "glucose", "visit": "L-3"},
    )
    assert preflight.status_code == 404
    assert "R+1, R+45, R+82, R+194" in preflight.json()["detail"]

    # An unencoded "+" in a URL arrives as a space; the message explains it.
    unencoded = client.get(f"{BASE}/astronauts/C001/postflight?panel=cmp&visit=R+1")
    assert unencoded.status_code == 404
    assert "%2B" in unencoded.json()["detail"]


def test_every_response_is_strict_json_with_numbers_as_strings_or_null():
    numeric = {
        "measurements": ["value", "lab_ref_min", "lab_ref_max", "normalized_percent"],
        "results": ["current_value", "baseline_value", "absolute_change",
                    "percentage_change", "lab_ref_min", "lab_ref_max"],
    }
    panels = ["cmp", "eve_cardiovascular", "eve_immune", "alamar_immune"]
    for crew in ["C001", "C002", "C003", "C004"]:
        for panel in panels:
            for endpoint, key in [("measurements", "measurements"), ("postflight", "results")]:
                response = client.get(f"{BASE}/astronauts/{crew}/{endpoint}", params={"panel": panel})
                assert response.status_code == 200
                data = response.json()
                json.dumps(data, allow_nan=False)  # fails on NaN or Infinity
                assert set(data) - {key, "crew_id", "panel", "biomarker", "visit", "count"} == ENVELOPE
                for record in data[key]:
                    for field in numeric[key]:
                        value = record[field]
                        assert value is None or Decimal(value).is_finite(), (crew, panel, field)


def test_missing_data_file_gives_clear_503_without_server_paths(monkeypatch, tmp_path):
    monkeypatch.setenv(osd575.DATA_DIR_ENV_VAR, str(tmp_path))

    response = client.get(f"{BASE}/astronauts")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv" in detail
    assert osd575.DATA_DIR_ENV_VAR in detail
    assert str(tmp_path) not in detail
    assert client.get("/health").status_code == 200


def test_failed_load_is_not_cached(monkeypatch, tmp_path):
    monkeypatch.setenv(osd575.DATA_DIR_ENV_VAR, str(tmp_path))
    assert client.get(f"{BASE}/astronauts").status_code == 503

    monkeypatch.delenv(osd575.DATA_DIR_ENV_VAR)

    assert client.get(f"{BASE}/astronauts").status_code == 200


def test_loading_and_analysis_work_with_network_blocked(monkeypatch):
    # The network is blocked only around loading and analysis, the code that
    # could otherwise fetch data. The test client itself cannot run under
    # this block: on Windows, asyncio opens a local socket pair for its event
    # loop.
    def no_network(*args, **kwargs):
        raise OSError("network blocked by test")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)

    data = osd575.get_data()

    assert len(data.analyses["C001", "cmp", "glucose"]) == 4
    assert sum(len(results) for results in data.analyses.values()) == 4832


def test_dataset_is_loaded_once_for_many_requests(monkeypatch):
    calls = []
    original = osd575.load_osd575

    def counting_loader(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(osd575, "load_osd575", counting_loader)

    get_ok(f"{BASE}/astronauts")
    get_ok(f"{BASE}/panels")
    get_ok(f"{BASE}/astronauts/C002/measurements", panel="eve_immune")

    assert len(calls) == 1
