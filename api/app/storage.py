"""Personal data storage: profile sessions, stored check-ins and "Plan for today" marks.

Every personal row has exactly one owner: the astronaut_id of the profile session
that wrote it. Nothing else in the database identifies an astronaut.

migrate() creates the tables that are missing and records the schema version. It
never drops, rewrites or reassigns existing tables or rows, so the app runs it on
every start, and it can also be run by hand (from api/):

    .venv\\Scripts\\python.exe -m app.storage

That command also reports what the database holds.
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any

from app.db import get_db_path, transaction

SCHEMA_VERSION = 1
_SCHEMA = (
    # The browser keeps a random session ID; only its SHA-256 hash is stored here.
    """CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY,
        astronaut_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    )""",
    # One row per check-in that A's engine assessed: the validated request and the result.
    """CREATE TABLE IF NOT EXISTS checkins (
        id INTEGER PRIMARY KEY,
        astronaut_id TEXT NOT NULL,
        received_at TEXT NOT NULL,
        check_in TEXT NOT NULL,
        assessment TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS checkins_by_owner ON checkins (astronaut_id, received_at)",
    # Tasks the astronaut ticks themself in "Plan for today", per UTC day.
    """CREATE TABLE IF NOT EXISTS plan_marks (
        astronaut_id TEXT NOT NULL,
        day TEXT NOT NULL,
        task TEXT NOT NULL,
        done INTEGER NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (astronaut_id, day, task)
    )""",
)


def now() -> str:
    """The current UTC time, to the second, as ISO 8601 (sorts correctly as text)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def migrate(conn: sqlite3.Connection) -> int:
    """Create missing personal tables and set the schema version. Safe to repeat."""
    for statement in _SCHEMA:
        conn.execute(statement)
    if conn.execute("PRAGMA user_version").fetchone()[0] < SCHEMA_VERSION:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return SCHEMA_VERSION


def save_checkin(astronaut_id: str, check_in: dict[str, Any], assessment: dict[str, Any]) -> str:
    """Store one assessed check-in for its owner and return the time it was received."""
    received_at = now()
    with transaction() as conn:
        migrate(conn)
        conn.execute(
            "INSERT INTO checkins (astronaut_id, received_at, check_in, assessment) VALUES (?, ?, ?, ?)",
            (astronaut_id, received_at, json.dumps(check_in), json.dumps(assessment)),
        )
    return received_at


def list_checkins(astronaut_id: str, limit: int) -> list[dict[str, Any]]:
    """The owner's most recent check-ins, newest first. Other owners' rows are never read."""
    with transaction() as conn:
        migrate(conn)
        rows = conn.execute(
            "SELECT id, received_at, check_in, assessment FROM checkins"
            " WHERE astronaut_id = ? ORDER BY received_at DESC, id DESC LIMIT ?",
            (astronaut_id, limit),
        ).fetchall()
    return [
        {"id": row[0], "received_at": row[1], "check_in": json.loads(row[2]), "assessment": json.loads(row[3])}
        for row in rows
    ]


def plan_for(astronaut_id: str, day: str) -> dict[str, Any]:
    """The owner's "Plan for today" on one UTC day (YYYY-MM-DD).

    The check-in, sleep and mood tasks come from the stored check-ins received
    that day, so only an assessed check-in counts, and an optional task only
    when a check-in included that value. "review" is ticked by the astronaut.
    """
    with transaction() as conn:
        migrate(conn)
        rows = conn.execute(
            "SELECT received_at, check_in FROM checkins"
            " WHERE astronaut_id = ? AND substr(received_at, 1, 10) = ? ORDER BY received_at",
            (astronaut_id, day),
        ).fetchall()
        mark = conn.execute(
            "SELECT done FROM plan_marks WHERE astronaut_id = ? AND day = ? AND task = 'review'",
            (astronaut_id, day),
        ).fetchone()
    indicators = [json.loads(text)["indicators"] for _, text in rows]
    tasks = {
        "checkin": {"done": bool(rows), "at": rows[-1][0] if rows else None},
        "sleep": {"done": any("sleep_duration" in i for i in indicators)},
        "mood": {"done": any("mood" in i for i in indicators)},
        "review": {"done": bool(mark and mark[0])},
    }
    return {
        "astronaut_id": astronaut_id,
        "day": day,
        "tasks": tasks,
        "done_count": sum(task["done"] for task in tasks.values()),
        "task_count": len(tasks),
    }


def set_plan_mark(astronaut_id: str, day: str, task: str, done: bool) -> None:
    with transaction() as conn:
        migrate(conn)
        conn.execute(
            "INSERT INTO plan_marks (astronaut_id, day, task, done, updated_at) VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT (astronaut_id, day, task) DO UPDATE SET done = excluded.done, updated_at = excluded.updated_at",
            (astronaut_id, day, task, int(done), now()),
        )


def report(conn: sqlite3.Connection) -> list[str]:
    """What the database holds, per table, and which rows have no owner."""
    lines = []
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
    for table in tables:
        count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]  # names come from sqlite_master
        lines.append(f"{table}: {count} rows")
    for table in ("checkins", "plan_marks", "sessions"):
        if table in tables:
            owners = conn.execute(f"SELECT astronaut_id, COUNT(*) FROM {table} GROUP BY astronaut_id").fetchall()
            lines.append(f"  {table} by owner: " + (", ".join(f"{a} {n}" for a, n in owners) or "none"))
    if "records" in tables:
        lines.append("  records (audit hash chain): no owner field; left unchanged and not shown in any workspace")
    return lines


def main() -> None:
    path = get_db_path()
    with transaction() as conn:
        before = conn.execute("PRAGMA user_version").fetchone()[0]
        migrate(conn)
        lines = report(conn)
    print(f"Database: {path.name} (schema version {before} -> {SCHEMA_VERSION}). Nothing was deleted or reassigned.")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
