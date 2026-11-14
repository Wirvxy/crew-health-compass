# Crew Health Compass API

This is the backend foundation: a FastAPI app with one liveness endpoint, plus a SQLite transaction helper. Owner: D.

| Path | Purpose |
|---|---|
| `app/main.py` | FastAPI app with `GET /health` |
| `app/db.py` | Database path setting and the `transaction()` helper |
| `tests/` | pytest tests, all using temporary databases |
| `requirements.txt` | Runtime dependencies, pinned |
| `requirements-dev.txt` | Runtime and test dependencies, pinned |
| `pytest.ini` | Tells pytest where the tests and the code are |

## Requirements

You need Python 3.11 or newer, because FastAPI 0.162.7 requires it. These instructions were verified only on Windows 10 with Python 3.14.3 in PowerShell.

## Set up (Windows PowerShell)

From the repository root:

```powershell
cd api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

`.venv` is a private Python environment for this folder, and Git ignores it. The commands call `.venv`'s own Python directly, so you don't need to "activate" the environment.

## Run the tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected result: `10 passed`, plus one Starlette deprecation warning (see [Known issues](#known-issues)).

CI (`.github/workflows/ci.yml`, job `backend`) runs the same install and test commands on Linux with Python 3.11 and 3.14, then runs pip-audit.

## Launch the server

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app
```

The server listens on `http://127.0.0.1:8000`, which is reachable only from this computer. To check it, run this in a second PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected result: a `status` column showing `ok`. Press Ctrl+C in the first window to stop the server.

## Configuration

| Environment variable | Meaning | Default |
|---|---|---|
| `CREW_HEALTH_DB_PATH` | Path of the SQLite database file | `api/crew_health.db` (Git ignores `*.db`) |

To set it for the current PowerShell window, run `$env:CREW_HEALTH_DB_PATH = "C:\path\to\crew_health.db"`. The folder must already exist. The tests check that the path is read from this variable.

## Doing database work

Put every piece of database work inside `transaction()`:

```python
from app.db import transaction

with transaction() as conn:
    conn.execute("INSERT INTO some_table (name) VALUES (?)", (name,))
```

- When the block finishes, the changes are committed (saved).
- When the block raises an error, the changes are rolled back (undone), and the error is passed on.
- The connection is closed in both cases. Python's own `with sqlite3.connect(...)` does not close it.
- Always use `?` placeholders. Never build SQL by joining strings (AGENTS.md section 6).

No tables exist yet. The schema waits for the contracts the team freezes at G1.

## What `/health` means

`GET /health` returning `{"status": "ok"}` means only that the server process is running and answering HTTP requests. It does not open the database, assess any health data, or prove that other parts of the system work.

## Dependencies

| Package | Licence | Why |
|---|---|---|
| `fastapi==0.162.7` | MIT | Web framework. It also installs pydantic (data validation) and starlette (HTTP handling). |
| `uvicorn==0.54.0` | BSD-3-Clause | The server process that runs the app |
| `pytest==9.2.0` | MIT | Test runner (tests only) |
| `httpx==0.28.1` | BSD-3-Clause | Needed by FastAPI's `TestClient` (tests only) |

- **Sub-dependencies:** these four install 19 more packages, all under permissive licences: MIT, BSD, Apache-2.0, PSF-2.0, and MPL-2.0 for `certifi`. Only the four direct dependencies are pinned. Sub-dependency versions are chosen at install time.
- **Vulnerabilities:** after installing the requirements, CI saves the exact installed list with `pip freeze`. It then audits that list with `pip-audit -r <list> --no-deps --disable-pip`, which fails on any known vulnerability.
  - This replaced `pip-audit -r requirements-dev.txt`, which silently left out `packaging`. That mode builds its own temporary environment, installs `wheel` there (which brings `packaging`), and then audits only the packages it would still need to install.
  - A local run of the new method with pip-audit 2.10.1 on 14 November 2026 audited all 23 installed packages, including `packaging` 26.3, and found no known vulnerabilities.
  - `pip freeze` leaves out pip, setuptools and wheel. Those are install tools, not app dependencies, and are not audited.
- **Telemetry:** FastAPI 0.162.7 installs `opentelemetry-api`. It can export data only when `FASTAPI_OTEL_AUTO_CONFIGURE=true` and an export endpoint are set *and* the OpenTelemetry SDK and exporter packages are installed. None of these are present, so nothing is sent.

## Known issues

- Starlette 1.10 warns that using `httpx` with its test client is deprecated, and suggests `httpx2`. The tests still pass. Switching would add a new dependency, which should be checked first.

## Not built yet (on purpose)

- Measurement, status, history, catalogue, report, audit and demo endpoints. These wait for the contracts at G1.
- Database tables, demo access control, plausibility checks, the audit chain, encryption and report signing.
- Python linting (ruff) in CI, and deployment (Docker).
- Instructions verified on macOS or Linux. On those systems, `.venv/bin/python` should replace `.\.venv\Scripts\python.exe`, but this has not been tested.
