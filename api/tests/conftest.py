"""Shared test setup.

Every test gets its own temporary database, so tests never read or write the
team's api/crew_health.db (sessions, stored check-ins and plan marks included).
Tests that check the database path setting change the variable themselves.
"""

import pytest
from fastapi.testclient import TestClient

from app import db, monitoring
from app.main import app


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch, tmp_path):
    monkeypatch.setenv(db.DB_PATH_ENV_VAR, str(tmp_path / "test.db"))


def signed_in(client: TestClient, astronaut: str) -> TestClient:
    """Open a profile session; the client then sends its cookie with every request."""
    response = client.post("/api/session", json={"astronaut_id": astronaut})
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def app_client(monkeypatch):
    """A client with the app's startup step run, and no session yet."""
    monkeypatch.delenv(monitoring.DATA_ENV_VAR, raising=False)
    with TestClient(app) as client:
        yield client
