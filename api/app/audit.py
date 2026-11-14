"""Hash-chained record storage (the audit log).

Every stored record is one row in the ``records`` table. Each row keeps:

- its data: a ``kind``, a JSON ``payload`` and the time it was recorded
- ``prev_hash``: the hash of the row before it (64 zeros for the first row)
- ``hash``: a SHA-256 fingerprint of the row's own fields and ``prev_hash``

``verify_chain()`` recomputes every hash in order and reports the first row
that does not match.

What a valid chain shows: since each row was written, no row has been edited,
removed from the middle or reordered, unless the hashes of every later row
were also recomputed.

What it does not show:
- The hash uses no secret key, so anyone who can write to the database file
  can change a row and recompute every later hash. Catching that needs the
  latest hash stored somewhere else, or signed (future work).
- Deleting rows from the end leaves a shorter chain that is still valid.
- Whether a value was correct when it was written.
"""

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

GENESIS_HASH = "0" * 64

_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY,
    recorded_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
)
"""


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the records table if it does not exist yet."""
    conn.execute(_SCHEMA)


def compute_hash(
    record_id: int, recorded_at: str, kind: str, payload: str, prev_hash: str
) -> str:
    """Return the SHA-256 hash of one record's fields as 64 hex characters.

    The fields are encoded together as one JSON array. That way the boundary
    between two fields is never ambiguous: different records always produce
    different bytes.
    """
    encoded = json.dumps(
        [record_id, recorded_at, kind, payload, prev_hash],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def append_record(conn: sqlite3.Connection, kind: str, payload: dict[str, Any]) -> int:
    """Add one record to the end of the chain and return its id.

    Call this inside ``db.transaction()``. The new id is the last id + 1, and
    the primary key forbids duplicate ids, so two appends can never both
    store the same id. If two appends overlap, one of them can fail (with a
    duplicate-id error, or SQLite reporting the database as locked), and its
    transaction is rolled back. The caller must handle that failure, for
    example by retrying. No retry exists yet, and concurrent appends have not
    been tested.
    """
    create_schema(conn)
    last = conn.execute(
        "SELECT id, hash FROM records ORDER BY id DESC LIMIT 1"
    ).fetchone()
    record_id, prev_hash = (last[0] + 1, last[1]) if last else (1, GENESIS_HASH)
    recorded_at = datetime.now(timezone.utc).isoformat()
    payload_text = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    record_hash = compute_hash(record_id, recorded_at, kind, payload_text, prev_hash)
    conn.execute(
        "INSERT INTO records (id, recorded_at, kind, payload, prev_hash, hash)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (record_id, recorded_at, kind, payload_text, prev_hash, record_hash),
    )
    return record_id


@dataclass(frozen=True)
class ChainCheck:
    """Result of verify_chain()."""

    valid: bool
    records_checked: int
    first_broken_id: int | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        if self.valid:
            return {"valid": True, "records_checked": self.records_checked}
        return {
            "valid": False,
            "first_broken_id": self.first_broken_id,
            "reason": self.reason,
        }


def verify_chain(conn: sqlite3.Connection) -> ChainCheck:
    """Recompute every record's hash in order and report the first mismatch."""
    create_schema(conn)
    rows = conn.execute(
        "SELECT id, recorded_at, kind, payload, prev_hash, hash FROM records ORDER BY id"
    )
    expected_prev = GENESIS_HASH
    checked = 0
    for record_id, recorded_at, kind, payload, prev_hash, stored_hash in rows:
        checked += 1
        if prev_hash != expected_prev:
            return ChainCheck(
                False, checked, record_id, "link to the previous record does not match"
            )
        if compute_hash(record_id, recorded_at, kind, payload, prev_hash) != stored_hash:
            return ChainCheck(
                False, checked, record_id, "record content does not match its stored hash"
            )
        expected_prev = stored_hash
    return ChainCheck(True, checked)
