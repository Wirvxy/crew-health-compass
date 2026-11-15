"""FastAPI application.

So far it has a liveness endpoint, the audit-chain check, read-only
endpoints for the NASA OSD-575 dataset (app/osd575.py, Mode 2), the
Mode 1 check-in assessment against synthetic history (app/monitoring.py),
and read-only Mars radiation history (app/radiation.py, Mission Environment).
Profile sessions (app/sessions.py) separate the four crew workspaces: each
astronaut's check-ins and daily plan are stored for that astronaut only
(app/storage.py, app/personal.py). This is demo access control: there are
no passwords. The NASA reference endpoints need no session.
"""

import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app import audit, monitoring, osd575, personal, radiation, sessions, storage
from app.db import transaction

logger = logging.getLogger(__name__)


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
    try:  # create any missing personal tables; never deletes or reassigns rows
        with transaction() as conn:
            storage.migrate(conn)
    except sqlite3.Error:
        logger.exception("Personal storage is not available; personal endpoints will fail until it is")
    yield
    radiation.clear_history()
    monitoring.clear_history()
    osd575.clear_dataset()


app = FastAPI(title="Crew Health Compass API", version="0.1.0", lifespan=lifespan)
app.include_router(osd575.router)
app.include_router(monitoring.router)
app.include_router(radiation.router)
app.include_router(sessions.router)
app.include_router(personal.router)


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
    A must confirm it. It needs no profile session: it reports only whether the
    chain is intact and how many records it holds, no personal data.

    - Intact chain: {"valid": true, "records_checked": <count>}
    - Broken chain: {"valid": false, "first_broken_id": <id>, "reason": "..."}
    """
    with transaction() as conn:
        result = audit.verify_chain(conn)
    return result.as_dict()
