"""FastAPI application.

So far there is only a liveness endpoint. Measurement endpoints will be added
once the team freezes the shared contracts at G1.
"""

from fastapi import FastAPI

app = FastAPI(title="Crew Health Compass API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the server process is running and answering requests.

    This is a liveness check only. It does not open the database, assess any
    health data, or prove that other parts of the system work.
    """
    return {"status": "ok"}
