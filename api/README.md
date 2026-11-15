# Crew Health Compass API

This is the backend foundation: a FastAPI app with a liveness endpoint, a SQLite transaction helper, a hash-chained audit log, read-only endpoints for the NASA OSD-575 dataset (Mode 2), and the Mode 1 check-in assessment against synthetic history. Owner: Monssif El Haouari (D). The frontend guide is [docs/mode1-api.md](../docs/mode1-api.md).

| Path | Purpose |
|---|---|
| `app/main.py` | FastAPI app with `GET /health` and `GET /audit/verify`. It also includes the OSD-575 routes |
| `app/db.py` | Database path setting and the `transaction()` helper |
| `app/audit.py` | Hash-chained `records` table: append and verify |
| `app/osd575.py` | Read-only `/datasets/osd575/...` endpoints built on A's `engine/`: astronauts, panels, measurements, postflight, trajectory, comparison and the A4 passport (see [docs/osd575-api.md](../docs/osd575-api.md)) |
| `app/monitoring.py` | Mode 1: `GET /api/monitoring/astronauts` and `POST /api/monitoring/assess`, built on A's M2 statistical detection and B's synthetic history (see [docs/mode1-api.md](../docs/mode1-api.md)) |
| `app/checkin_checks.py` | Format and logic checks that the API adds to a Mode 1 check-in. They are not medical limits |
| `app/radiation.py` | Mission Environment: `GET /api/environment/radiation/timeline` and `GET /api/environment/radiation/events/may-20-2024`, built on A's R1 radiation history engine (see [docs/radiation-api.md](../docs/radiation-api.md)) |
| `tests/` | pytest tests. Database tests use temporary databases; OSD-575 tests read `data/mode2/` |
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

Expected result: `152 passed`, plus one Starlette deprecation warning (see [Known issues](#known-issues)). `pytest.ini` adds the repository root to the import path, so the tests can import A's `engine/`.

A's engine has its own `unittest` suite (78 tests; 5 are skipped unless the optional scikit-learn for the disabled M3 experiment is installed). Run it from the repository root:

```powershell
api\.venv\Scripts\python.exe -m unittest discover -s engine
```

CI (`.github/workflows/ci.yml`, job `backend`) runs both suites on Linux with Python 3.11 and 3.14: first A's engine tests from the repository root, then pytest from `api/`. It then runs pip-audit.

## Launch the server

Run this **from the repository root**, not from `api/`, so that A's `engine/` can be imported:

```powershell
api\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir api
```

The old command, run from `api/`, now stops with `ModuleNotFoundError: No module named 'engine'`.

At startup the server loads the OSD-575 CSVs once and runs A's analyses (about 0.2 s), then loads B's synthetic Mode 1 history once (about 0.2 s), then the Curiosity RAD radiation CSV. If any dataset is missing or unusable:
- The server still starts, and `/health` still answers.
- The affected endpoints (`/datasets/osd575/...`, `/api/monitoring/...` or `/api/environment/radiation/...`) return 503, naming the problem without any server path.
- The error is written to the server log.

Fix the files, then **restart the server**. It doesn't re-read them while running.

The server listens on `http://127.0.0.1:8000`, which is reachable only from this computer. To check it, run this in a second PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected result: a `status` column showing `ok`. Press Ctrl+C in the first window to stop the server.

## Configuration

| Environment variable | Meaning | Default |
|---|---|---|
| `CREW_HEALTH_DB_PATH` | Path of the SQLite database file | `api/crew_health.db` (Git ignores `*.db`) |
| `CREW_HEALTH_OSD575_DIR` | Folder holding the four OSD-575 `*_TRANSFORMED.csv` files | the repository's `data/mode2/` |
| `CREW_HEALTH_MODE1_DATA` | Folder or ZIP holding B's synthetic `iss-synthetic-3000` dataset | the repository's `data/mode1/` |
| `CREW_HEALTH_RAD_CSV` | The Curiosity RAD radiation CSV (Mission Environment) | `data/radiation/nasa_curiosity_rad_2024-03-07_to_2024-05-20.csv` |

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

The only table so far is `records`, the audit log described below. Measurement fields wait for the contracts the team freezes at G1.

## Audit log (hash chain)

Stored records go in one append-only table, `records`, through `audit.append_record(conn, kind, payload)`. The chain covers only records added this way. Measurement writes are not connected to it yet, because they wait for the G1 contracts.
- Each row keeps its data (`kind`, a JSON `payload`, `recorded_at`), the hash of the row before it (`prev_hash`, 64 zeros for the first row), and its own SHA-256 `hash`.
- The hash covers the row's id, time, kind, payload and `prev_hash`, so every row is locked to the one before it.

`GET /audit/verify` recomputes every hash in order:
- Intact chain: `{"valid": true, "records_checked": 3}`
- Broken chain: `{"valid": false, "first_broken_id": 2, "reason": "record content does not match its stored hash"}`

This response shape is **provisional**: it is not in the shared contracts yet, and A must confirm it. Until demo access control exists, any caller can use the endpoint.

**What a valid chain shows:** since each row was written, no row has been edited, removed from the middle or reordered, unless the hashes of every later row were also recomputed.

**What it does not show:**
- The hash uses no secret key. Anyone who can write to the database file can change a row and then recompute every later hash, and the chain will look valid again. A test (`test_limit_rewriting_every_later_hash_is_not_detected`) documents this. Catching it needs the latest hash kept somewhere else, or signed (future work).
- Deleting rows from the end leaves a shorter chain that is still valid (`test_limit_deleting_the_last_record_is_not_detected`).
- Whether a value was correct when it was written. That is the job of input validation, which is not built yet.

**Concurrent writes:** if two appends overlap, one of them can fail (a duplicate id, or "database is locked") and is rolled back. The caller has to handle that, for example by retrying. No retry exists yet, and concurrent appends have not been tested.

To try it, launch the server with `CREW_HEALTH_DB_PATH` pointing at a test database that has a few records. Change one record's `payload` with any SQLite tool, then call `Invoke-RestMethod http://127.0.0.1:8000/audit/verify`.

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

- Storing check-ins, and the status, history, catalogue, report and demo endpoints. These wait for the contracts at G1. The Mode 1 assessment works without storage, and the OSD-575 endpoints are separate.
- Measurement tables, demo access control, plausibility checks, encryption and report signing.
- Protection for the audit chain's latest hash (an outside copy or a signature).
- Python linting (ruff) in CI, and deployment (Docker).
- Instructions verified on macOS or Linux. On those systems, `.venv/bin/python` should replace `.\.venv\Scripts\python.exe`, but this has not been tested.
