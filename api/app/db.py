"""SQLite connection handling.

Run every piece of database work inside ``transaction()``. It opens a
connection, runs the work as one transaction, and always closes the
connection, even when something goes wrong.

The database file comes from the ``CREW_HEALTH_DB_PATH`` environment variable.
If that variable is not set, the file is ``api/crew_health.db``, which Git
ignores.
"""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DB_PATH_ENV_VAR = "CREW_HEALTH_DB_PATH"
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "crew_health.db"


def get_db_path() -> Path:
    """Return the database file path, reading the environment on every call."""
    value = os.environ.get(DB_PATH_ENV_VAR)
    return Path(value) if value else DEFAULT_DB_PATH


@contextmanager
def transaction(
    db_path: str | os.PathLike[str] | None = None,
) -> Iterator[sqlite3.Connection]:
    """Run a block of database work as one all-or-nothing transaction.

    - If the block finishes normally, the changes are committed (saved).
    - If the block raises an exception, the changes are rolled back (undone),
      and the same exception is raised again.
    - In both cases, the connection is closed afterwards.

    Python's ``with sqlite3.connect(...) as conn:`` commits or rolls back, but
    it does not close the connection. That is why this helper exists.
    """
    path = Path(db_path) if db_path is not None else get_db_path()
    # isolation_level=None stops the sqlite3 module from opening transactions
    # by itself, so the BEGIN, COMMIT and ROLLBACK below are the only ones.
    conn = sqlite3.connect(path, isolation_level=None)
    try:
        conn.execute("BEGIN")
        try:
            yield conn
        except BaseException:
            # After some errors SQLite has already rolled back by itself.
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
    finally:
        conn.close()
