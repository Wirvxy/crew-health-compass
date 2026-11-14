"""Tests for app.db: path configuration, commit, rollback and cleanup.

Every test uses a new database file in pytest's temporary folder (tmp_path),
so no test touches a real database. The "items" table exists only in these
tests. It is not the project's data model.
"""

import sqlite3
from contextlib import closing

import pytest

from app import db


@pytest.fixture
def db_file(tmp_path):
    path = tmp_path / "test.db"
    with db.transaction(path) as conn:
        conn.execute("CREATE TABLE items (name TEXT NOT NULL)")
    return path


def count_items(path):
    # A plain connection, independent of the code under test.
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]


def test_db_path_comes_from_environment(monkeypatch, tmp_path):
    configured = tmp_path / "configured.db"
    monkeypatch.setenv(db.DB_PATH_ENV_VAR, str(configured))

    assert db.get_db_path() == configured


def test_db_path_defaults_to_api_folder(monkeypatch):
    monkeypatch.delenv(db.DB_PATH_ENV_VAR, raising=False)

    assert db.get_db_path() == db.DEFAULT_DB_PATH
    assert db.DEFAULT_DB_PATH.parent.name == "api"


def test_transaction_uses_configured_path(monkeypatch, tmp_path):
    configured = tmp_path / "from-env.db"
    monkeypatch.setenv(db.DB_PATH_ENV_VAR, str(configured))

    with db.transaction() as conn:
        conn.execute("CREATE TABLE items (name TEXT NOT NULL)")
        conn.execute("INSERT INTO items VALUES ('saved')")

    assert count_items(configured) == 1


def test_commit_saves_changes(db_file):
    with db.transaction(db_file) as conn:
        conn.execute("INSERT INTO items VALUES ('first')")
        conn.execute("INSERT INTO items VALUES ('second')")

    assert count_items(db_file) == 2


def test_rollback_on_exception_discards_changes(db_file):
    with pytest.raises(RuntimeError, match="stop here"):
        with db.transaction(db_file) as conn:
            conn.execute("INSERT INTO items VALUES ('not kept')")
            raise RuntimeError("stop here")

    assert count_items(db_file) == 0


def test_rollback_on_sql_error_undoes_earlier_statements(db_file):
    # The first insert is valid. The second breaks the NOT NULL rule, so the
    # whole transaction is undone, including the valid first insert.
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction(db_file) as conn:
            conn.execute("INSERT INTO items VALUES ('valid')")
            conn.execute("INSERT INTO items VALUES (NULL)")

    assert count_items(db_file) == 0


def test_connection_is_closed_after_commit(db_file):
    with db.transaction(db_file) as conn:
        conn.execute("INSERT INTO items VALUES ('x')")

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_connection_is_closed_after_rollback(db_file):
    with pytest.raises(RuntimeError):
        with db.transaction(db_file) as conn:
            raise RuntimeError("fail")

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
