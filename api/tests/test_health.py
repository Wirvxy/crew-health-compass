"""Tests for the GET /health liveness endpoint."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_need_the_database(monkeypatch, tmp_path):
    # Point the database at a folder that does not exist. /health must still
    # answer, because it only reports that the server process is running.
    missing = tmp_path / "missing-folder" / "crew_health.db"
    monkeypatch.setenv("CREW_HEALTH_DB_PATH", str(missing))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert not missing.parent.exists()
