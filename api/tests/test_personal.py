"""Tests for personal workspaces: stored check-ins, plans and ownership (app/personal.py, app/storage.py)."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import db, storage
from app.main import app
from conftest import signed_in

URL = "/api/monitoring/assess"
TODAY = datetime.now(timezone.utc).date()


def check_in(astronaut="commander", heart_rate="67", sleep=True, mood=True):
    indicators = {
        "heart_rate": {"value": heart_rate, "unit": "bpm"}, "respiratory_rate": {"value": "15", "unit": "breaths/min"},
        "systolic_bp": {"value": "100", "unit": "mmHg"}, "diastolic_bp": {"value": "59", "unit": "mmHg"},
    }
    if sleep:
        indicators["sleep_duration"] = {"value": "7.5", "unit": "h"}
    if mood:
        indicators["mood"] = "good"
    return {"astronaut_id": astronaut, "timestamp": "2030-06-30T13:30:00Z", "activity_context": "rest", "indicators": indicators}


@pytest.fixture
def crew(app_client):
    """Two browsers: the commander and flight engineer 1, each with its own session cookie."""
    commander = signed_in(app_client, "commander")
    engineer = signed_in(TestClient(app), "flight_engineer_1")  # the data loaded by app_client's startup is shared
    return commander, engineer


def plan(client, day=TODAY):
    return client.get(f"/api/me/plan?day={day.isoformat()}").json()


def test_a_check_in_is_stored_only_for_its_owner(crew):
    commander, engineer = crew
    result = commander.post(URL, json=check_in()).json()
    mine = commander.get("/api/me/checkins").json()
    assert mine["astronaut_id"] == "commander" and len(mine["checkins"]) == 1
    stored = mine["checkins"][0]
    assert stored["assessment"] == result and stored["check_in"]["astronaut_id"] == "commander"
    assert stored["received_at"].startswith(TODAY.isoformat())
    assert engineer.get("/api/me/checkins").json() == {"astronaut_id": "flight_engineer_1", "checkins": []}


def test_a_check_in_naming_another_astronaut_is_refused_and_not_stored(crew):
    commander, engineer = crew
    response = engineer.post(URL, json=check_in(astronaut="commander"))
    assert response.status_code == 403
    assert commander.get("/api/me/checkins").json()["checkins"] == []
    assert engineer.get("/api/me/checkins").json()["checkins"] == []


@pytest.mark.parametrize("path", [
    "/api/me/checkins?astronaut_id=commander",
    "/api/me/checkins?astronaut=commander&crew=commander",
    "/api/me/plan?day={today}&astronaut_id=commander",
    "/api/monitoring/astronauts?astronaut_id=commander",
])
def test_a_crew_id_in_the_query_cannot_reach_another_profile(crew, path):
    commander, engineer = crew
    commander.post(URL, json=check_in())
    body = engineer.get(path.format(today=TODAY.isoformat())).json()
    assert "commander" not in str(body)


def test_plan_for_today_is_separate_per_astronaut(crew):
    commander, engineer = crew
    assert plan(commander)["done_count"] == 0
    commander.post(URL, json=check_in())
    mine = plan(commander)
    assert mine["done_count"] == 3 and mine["tasks"]["checkin"]["at"].startswith(TODAY.isoformat())
    assert mine["tasks"]["review"]["done"] is False
    response = commander.put("/api/me/plan/review", json={"day": TODAY.isoformat(), "done": True})
    assert response.json()["done_count"] == 4
    assert plan(engineer)["done_count"] == 0
    assert plan(engineer)["astronaut_id"] == "flight_engineer_1"


def test_optional_tasks_need_the_value_in_an_assessed_check_in(crew):
    commander, _ = crew
    commander.post(URL, json=check_in(sleep=False, mood=False))
    tasks = plan(commander)["tasks"]
    assert tasks["checkin"]["done"] and not tasks["sleep"]["done"] and not tasks["mood"]["done"]
    commander.post(URL, json=check_in(sleep=True, mood=False))
    tasks = plan(commander)["tasks"]
    assert tasks["sleep"]["done"] and not tasks["mood"]["done"]


def test_invalid_or_failed_check_ins_complete_nothing(crew):
    commander, _ = crew
    assert commander.post(URL, json=check_in(heart_rate="0")).status_code == 422
    assert commander.post(URL, json={"astronaut_id": "commander"}).status_code == 422
    assert plan(commander)["done_count"] == 0
    assert commander.get("/api/me/checkins").json()["checkins"] == []


def test_another_day_starts_empty(crew):
    commander, _ = crew
    commander.post(URL, json=check_in())
    commander.put("/api/me/plan/review", json={"day": TODAY.isoformat(), "done": True})
    assert plan(commander, TODAY + timedelta(days=1))["done_count"] == 0
    assert plan(commander, TODAY - timedelta(days=1))["done_count"] == 0


def test_review_can_be_unticked(crew):
    commander, _ = crew
    commander.put("/api/me/plan/review", json={"day": TODAY.isoformat(), "done": True})
    assert commander.put("/api/me/plan/review", json={"day": TODAY.isoformat(), "done": False}).json()["tasks"]["review"]["done"] is False


@pytest.mark.parametrize("day", ["today", "2026-13-01", "2026-11-15T00:00:00Z", "2026-02-30", ""])
def test_plan_day_must_be_a_date(crew, day):
    commander, _ = crew
    assert commander.get(f"/api/me/plan?day={day}").status_code == 422


@pytest.mark.parametrize("body", [{"day": "2026-11-15"}, {"day": "2026-11-15", "done": "yes"},
                                  {"day": "2026-11-15", "done": True, "astronaut_id": "commander"}, []])
def test_review_body_is_checked(crew, body):
    _, engineer = crew
    assert engineer.put("/api/me/plan/review", json=body).status_code == 422


def test_stored_check_ins_do_not_change_the_baseline(crew):
    commander, _ = crew
    first = commander.post(URL, json=check_in(heart_rate="85")).json()
    second = commander.post(URL, json=check_in(heart_rate="85")).json()
    hr = [next(e for e in r["evidence"] if e["indicator"] == "heart_rate") for r in (first, second)]
    assert hr[0]["baseline"] == hr[1]["baseline"]
    assert hr[0]["statistics"]["observation_count"] == hr[1]["statistics"]["observation_count"]


def test_a_check_in_that_cannot_be_saved_is_reported(crew, monkeypatch):
    commander, _ = crew
    def broken(*args, **kwargs):
        raise sqlite3.OperationalError("disk I/O error")
    monkeypatch.setattr(storage, "save_checkin", broken)
    response = commander.post(URL, json=check_in())
    assert response.status_code == 503 and "could not be saved" in response.json()["detail"]


def test_migration_is_repeatable_and_keeps_existing_records(tmp_path, monkeypatch, capsys):
    path = tmp_path / "existing.db"
    with sqlite3.connect(path) as conn:  # a database from before this change, with audit records
        conn.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, recorded_at TEXT, kind TEXT, payload TEXT, prev_hash TEXT, hash TEXT)")
        conn.execute("INSERT INTO records VALUES (1, 't', 'note', '{}', 'p', 'h')")
    monkeypatch.setenv(db.DB_PATH_ENV_VAR, str(path))
    storage.main()
    storage.main()
    out = capsys.readouterr().out
    assert "schema version 0 -> 1" in out and "schema version 1 -> 1" in out and "Nothing was deleted" in out
    assert "records (audit hash chain): no owner field" in out
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT * FROM records").fetchall() == [(1, "t", "note", "{}", "p", "h")]
        assert conn.execute("PRAGMA user_version").fetchone() == (1,)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"records", "sessions", "checkins", "plan_marks"} <= tables
