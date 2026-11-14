"""FastAPI application.

So far there are only a liveness endpoint and the audit-chain check.
Measurement endpoints will be added once the team freezes the shared
contracts at G1.
"""

from typing import Any

from fastapi import FastAPI

from app import audit
from app.db import transaction

app = FastAPI(title="Crew Health Compass API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the server process is running and answering requests.

    This is a liveness check only. It does not open the database, assess any
    health data, or prove that other parts of the system work.
    """
    return {"status": "ok"}


@app.get("/audit/verify")
def audit_verify() -> dict[str, Any]:
    """Check the hash chain of stored records (see app/audit.py).

    PROVISIONAL: this response shape is not yet in the shared contracts, and
    A must confirm it. Until demo access control exists, any caller can use
    this endpoint.

    - Intact chain: {"valid": true, "records_checked": <count>}
    - Broken chain: {"valid": false, "first_broken_id": <id>, "reason": "..."}
    """
    with transaction() as conn:
        result = audit.verify_chain(conn)
    return result.as_dict()
