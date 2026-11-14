"""Tests for the hash-chained audit log (app/audit.py) and GET /audit/verify.

Every test uses a new database in pytest's temporary folder. Tampering is
done with a plain sqlite3 connection, the way an attacker with access to the
database file would do it.
"""

import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app import audit, db
from app.main import app


@pytest.fixture
def chain(tmp_path):
    """A database with three chained records. Returns its path."""
    path = tmp_path / "audit.db"
    with db.transaction(path) as conn:
        for n in (1, 2, 3):
            audit.append_record(conn, "test", {"n": n})
    return path


def tamper(path, sql, params=()):
    """Change the database directly, bypassing the application."""
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(sql, params)
        conn.commit()


def check(path):
    with db.transaction(path) as conn:
        return audit.verify_chain(conn)


def row(path, record_id):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(
            "SELECT id, recorded_at, kind, payload, prev_hash, hash FROM records WHERE id = ?",
            (record_id,),
        ).fetchone()


def test_empty_chain_is_valid(tmp_path):
    result = check(tmp_path / "empty.db")

    assert result.valid
    assert result.records_checked == 0


def test_records_are_linked_in_order(chain):
    first, second = row(chain, 1), row(chain, 2)

    assert first[4] == audit.GENESIS_HASH
    assert second[4] == first[5]


def test_intact_chain_is_valid(chain):
    result = check(chain)

    assert result.valid
    assert result.records_checked == 3


@pytest.mark.parametrize(
    "sql, value",
    [
        ("UPDATE records SET payload = ? WHERE id = 2", '{"n":99}'),
        ("UPDATE records SET kind = ? WHERE id = 2", "edited"),
        ("UPDATE records SET recorded_at = ? WHERE id = 2", "2000-01-01T00:00:00+00:00"),
    ],
)
def test_editing_a_stored_field_is_detected(chain, sql, value):
    tamper(chain, sql, (value,))

    result = check(chain)

    assert not result.valid
    assert result.first_broken_id == 2
    assert result.reason == "record content does not match its stored hash"


def test_deleting_a_middle_record_is_detected(chain):
    tamper(chain, "DELETE FROM records WHERE id = 2")

    result = check(chain)

    assert not result.valid
    assert result.first_broken_id == 3
    assert result.reason == "link to the previous record does not match"


def test_recomputing_only_the_edited_hash_is_detected_at_the_next_record(chain):
    _, recorded_at, kind, _, prev_hash, _ = row(chain, 2)
    new_hash = audit.compute_hash(2, recorded_at, kind, '{"n":99}', prev_hash)
    tamper(chain, "UPDATE records SET payload = ?, hash = ? WHERE id = 2", ('{"n":99}', new_hash))

    result = check(chain)

    assert not result.valid
    assert result.first_broken_id == 3


def test_limit_rewriting_every_later_hash_is_not_detected(chain):
    # Documents a known limit: without a secret key or an outside copy of the
    # latest hash, a full rewrite from the edited record onward looks valid.
    _, recorded_at, kind, _, prev_hash, _ = row(chain, 2)
    hash_2 = audit.compute_hash(2, recorded_at, kind, '{"n":99}', prev_hash)
    tamper(chain, "UPDATE records SET payload = ?, hash = ? WHERE id = 2", ('{"n":99}', hash_2))
    _, recorded_at, kind, payload, _, _ = row(chain, 3)
    hash_3 = audit.compute_hash(3, recorded_at, kind, payload, hash_2)
    tamper(chain, "UPDATE records SET prev_hash = ?, hash = ? WHERE id = 3", (hash_2, hash_3))

    assert check(chain).valid


def test_limit_deleting_the_last_record_is_not_detected(chain):
    # Documents a known limit: a chain cut short at the end is still valid.
    tamper(chain, "DELETE FROM records WHERE id = 3")

    result = check(chain)

    assert result.valid
    assert result.records_checked == 2


def test_verify_endpoint_reports_intact_chain(chain, monkeypatch):
    monkeypatch.setenv(db.DB_PATH_ENV_VAR, str(chain))

    response = TestClient(app).get("/audit/verify")

    assert response.status_code == 200
    assert response.json() == {"valid": True, "records_checked": 3}


def test_verify_endpoint_names_first_broken_record(chain, monkeypatch):
    monkeypatch.setenv(db.DB_PATH_ENV_VAR, str(chain))
    tamper(chain, "UPDATE records SET payload = ? WHERE id = 2", ('{"n":99}',))

    response = TestClient(app).get("/audit/verify")

    assert response.status_code == 200
    assert response.json() == {
        "valid": False,
        "first_broken_id": 2,
        "reason": "record content does not match its stored hash",
    }
