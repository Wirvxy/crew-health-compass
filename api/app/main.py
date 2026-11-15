"""FastAPI application.

So far it has a liveness endpoint, the audit-chain check, read-only
endpoints for the NASA OSD-575 dataset (app/osd575.py, Mode 2), the
Mode 1 check-in assessment against synthetic history (app/monitoring.py),
and read-only Mars radiation history (app/radiation.py, Mission Environment).
Check-ins are assessed but not stored yet.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app import audit, monitoring, osd575, radiation
from app.db import transaction


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the three datasets once, before serving requests.

    No loader raises for missing or unusable data. /health keeps working,
    and only the affected endpoints answer 503 until the server is restarted
    with valid files.
    """
    osd575.load_dataset()
    monitoring.load_history()
    radiation.load_history()
    yield
    radiation.clear_history()
    monitoring.clear_history()
    osd575.clear_dataset()


app = FastAPI(title="Crew Health Compass API", version="0.1.0", lifespan=lifespan)
app.include_router(osd575.router)
app.include_router(monitoring.router)
app.include_router(radiation.router)


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
