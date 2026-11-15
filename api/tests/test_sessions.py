"""Tests for profile sessions (app/sessions.py): demo access control without passwords."""

import sqlite3

import pytest

from app import db, sessions
from conftest import signed_in

CHECK_IN = {
    "astronaut_id": "commander", "timestamp": "2030-06-30T13:30:00Z", "activity_context": "rest",
    "indicators": {"heart_rate": {"value": "67", "unit": "bpm"}, "respiratory_rate": {"value": "15", "unit": "breaths/min"},
                   "systolic_bp": {"value": "100", "unit": "mmHg"}, "diastolic_bp": {"value": "59", "unit": "mmHg"}},
}
PERSONAL = [
    ("GET", "/api/monitoring/astronauts", None),
    ("POST", "/api/monitoring/assess", CHECK_IN),
    ("GET", "/api/me/checkins", None),
    ("GET", "/api/me/plan?day=2026-11-15", None),
    ("PUT", "/api/me/plan/review", {"day": "2026-11-15", "done": True}),
]


def rows(query):
    with sqlite3.connect(db.get_db_path()) as conn:
        return conn.execute(query).fetchall()


def test_profiles_are_the_four_synthetic_crew_roles_without_personal_details(app_client):
    body = app_client.get("/api/profiles").json()
    assert body["profiles"] == [
        {"astronaut_id": "commander", "name": "Commander"},
        {"astronaut_id": "flight_engineer_1", "name": "Flight Engineer 1"},
        {"astronaut_id": "flight_engineer_2", "name": "Flight Engineer 2"},
        {"astronaut_id": "flight_engineer_3", "name": "Flight Engineer 3"},
    ]
    assert "password" in body["note"]


@pytest.mark.parametrize("method, path, body", PERSONAL)
def test_personal_endpoints_need_a_session(app_client, method, path, body):
    response = app_client.request(method, path, json=body)
    assert response.status_code == 401
    assert response.json()["detail"] == sessions.NO_SESSION


def test_opening_a_profile_sets_an_httponly_strict_cookie(app_client):
    assert app_client.get("/api/session").json() == {"profile": None}  # signed out is a normal answer
    response = app_client.post("/api/session", json={"astronaut_id": "flight_engineer_2"})
    assert response.json() == {"astronaut_id": "flight_engineer_2", "name": "Flight Engineer 2"}
    cookie = response.headers["set-cookie"].lower()
    assert "chc_session=" in cookie and "httponly" in cookie and "samesite=strict" in cookie and "path=/" in cookie
    assert "secure" not in cookie  # plain HTTP with the default "auto" setting
    assert app_client.get("/api/session").json()["profile"]["astronaut_id"] == "flight_engineer_2"


def test_secure_cookie_when_configured(app_client, monkeypatch):
    monkeypatch.setenv(sessions.SECURE_ENV_VAR, "true")
    response = app_client.post("/api/session", json={"astronaut_id": "commander"})
    assert "secure" in response.headers["set-cookie"].lower()


def test_only_a_hash_of_the_session_id_is_stored(app_client):
    signed_in(app_client, "commander")
    token = app_client.cookies.get(sessions.COOKIE)
    stored = rows("SELECT token_hash, astronaut_id FROM sessions")
    assert stored == [(sessions.hash_token(token), "commander")]
    assert token not in str(stored)


@pytest.mark.parametrize("body, status", [
    ({"astronaut_id": "C001"}, 422),  # a NASA study subject is not an app profile
    ({"astronaut_id": "nobody"}, 422),
    ({"astronaut_id": ["commander"]}, 422),
    ([], 422),
])
def test_only_known_profiles_can_be_opened(app_client, body, status):
    assert app_client.post("/api/session", json=body).status_code == status
    assert rows("SELECT COUNT(*) FROM sessions") == [(0,)]


def test_opening_a_profile_needs_json(app_client):
    response = app_client.post("/api/session", content='{"astronaut_id": "commander"}', headers={"content-type": "text/plain"})
    assert response.status_code == 415


@pytest.mark.parametrize("method, path, body", [
    ("POST", "/api/session", {"astronaut_id": "commander"}),
    ("DELETE", "/api/session", None),
    ("POST", "/api/monitoring/assess", CHECK_IN),
    ("PUT", "/api/me/plan/review", {"day": "2026-11-15", "done": True}),
])
@pytest.mark.parametrize("site", ["cross-site", "same-site"])
def test_changes_sent_from_another_website_are_refused(app_client, method, path, body, site):
    signed_in(app_client, "commander")
    response = app_client.request(method, path, json=body, headers={"sec-fetch-site": site})
    assert response.status_code == 403
    assert rows("SELECT COUNT(*) FROM checkins") == [(0,)]


def test_same_origin_browser_requests_are_accepted(app_client):
    response = app_client.post("/api/session", json={"astronaut_id": "commander"}, headers={"sec-fetch-site": "same-origin"})
    assert response.status_code == 200


def test_logout_ends_the_session_on_the_server(app_client):
    signed_in(app_client, "commander")
    token = app_client.cookies.get(sessions.COOKIE)
    response = app_client.delete("/api/session")
    assert response.json() == {"signed_out": True}
    assert 'chc_session=""' in response.headers["set-cookie"] or "max-age=0" in response.headers["set-cookie"].lower()
    assert rows("SELECT COUNT(*) FROM sessions") == [(0,)]
    app_client.cookies.set(sessions.COOKIE, token)  # replaying the old cookie no longer works
    assert app_client.get("/api/me/checkins").status_code == 401


def test_choosing_another_profile_ends_the_previous_session(app_client):
    signed_in(app_client, "commander")
    old = app_client.cookies.get(sessions.COOKIE)
    signed_in(app_client, "flight_engineer_1")
    assert rows("SELECT astronaut_id FROM sessions") == [("flight_engineer_1",)]
    app_client.cookies.set(sessions.COOKIE, old)
    assert app_client.get("/api/session").json() == {"profile": None}


def test_expired_sessions_stop_working_and_are_deleted(app_client):
    signed_in(app_client, "commander")
    with sqlite3.connect(db.get_db_path()) as conn:
        conn.execute("UPDATE sessions SET expires_at = '2000-01-01T00:00:00+00:00'")
    assert app_client.get("/api/me/checkins").status_code == 401
    assert rows("SELECT COUNT(*) FROM sessions") == [(0,)]


def test_a_made_up_cookie_is_not_a_session(app_client):
    app_client.cookies.set(sessions.COOKIE, "not-a-real-session")
    assert app_client.get("/api/session").json() == {"profile": None}
    assert app_client.get("/api/me/checkins").status_code == 401


def test_personal_answers_are_not_cached_and_name_their_owner(app_client):
    signed_in(app_client, "flight_engineer_3")
    response = app_client.get("/api/me/checkins")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers[sessions.PROFILE_HEADER] == "flight_engineer_3"


def test_reference_data_needs_no_session(app_client):
    assert app_client.get("/datasets/osd575/astronauts").status_code == 200
    assert app_client.get("/api/environment/radiation/events/may-20-2024").status_code == 200
