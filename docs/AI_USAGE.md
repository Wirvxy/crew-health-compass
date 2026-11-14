# AI usage log

The event requires a description of how AI tools were used. Every agent session gets an entry here with at least the date, member, tool, task, files changed and human review status. Add new entries at the bottom and keep earlier entries unchanged.

## 2026-11-14 · Member D · Claude Code · Initial frontend CI

- **Task:** Add the first GitHub Actions workflow. It runs on pull requests into `main` and on pushes to `main`, with read-only repository permissions. It installs the locked frontend dependencies, type-checks and builds the frontend, and audits dependencies.
- **Files changed:**
  - `.github/workflows/ci.yml` (new)
  - `docs/AI_USAGE.md` (new, this entry)
- **Local checks:** Run on Windows with Node 24.14.0 and npm 11.9.0, on a clean export of `frontend/` at commit `46fbaa6`.
  - `npm ci`: passed (exit 0).
  - `npm run build` (`tsc --noEmit && vite build`): passed (exit 0).
  - `npm audit --audit-level=high`: passed (exit 0, 0 vulnerabilities).
  - Negative tests in throwaway copies:
    - A deliberate type error made the build exit 1.
    - A test project locking `lodash@4.17.15` made the audit exit 1 (1 high-severity advisory).
  - Text checks on the workflow file: no tabs, LF line endings, actions pinned to full commit SHAs, and no `|| true` or `continue-on-error`. No YAML linter was run.
- **GitHub Actions result:** [CI run #1](https://github.com/Wirvxy/crew-health-compass/actions/runs/43597695679) on PR #4 (commit `65cc470`) passed in 13 s.
  - It ran on `ubuntu-26.04` with Node v24.22.2 and npm 11.19.1.
  - `npm ci` added 24 packages, the build transformed 17 modules, and `npm audit` found 0 vulnerabilities.
  - The log showed no errors or warnings.
- **Still pending:**
  - The push-to-`main` trigger runs only after this PR is merged.
  - Backend checks (ruff, pytest, pip-audit) wait until Python code and tests exist.
  - Secret scanning (gitleaks) is not part of this workflow yet.
- **Human review:** None yet.

## 2026-11-14 · Member D · Claude Code · Backend foundation

- **Task:** Create a minimal FastAPI app under `api/` with:
  - a `GET /health` liveness endpoint
  - a SQLite transaction helper whose database path comes from the `CREW_HEALTH_DB_PATH` environment variable
  - tests that use temporary databases
  - verified setup instructions

  No measurement endpoints, schemas, medical rules or token formats were added.
- **Files changed:**
  - `api/app/__init__.py`, `api/app/main.py`, `api/app/db.py` (new)
  - `api/tests/test_health.py`, `api/tests/test_db.py` (new)
  - `api/requirements.txt`, `api/requirements-dev.txt`, `api/pytest.ini`, `api/README.md` (new)
  - `docs/AI_USAGE.md` (this entry)
- **Dependencies added:**
  - Runtime: fastapi 0.162.7 and uvicorn 0.54.0.
  - Tests only: pytest 9.2.0 and httpx 0.28.1.
  - Licences were checked from package metadata, and all are permissive. Known vulnerabilities were not checked.
- **Local checks:** Run on Windows 10 with Python 3.14.3, in a fresh `api/.venv` built with the README commands.
  - `python -m pytest`: 10 passed, with 1 warning (a Starlette deprecation notice about `httpx`).
  - Launching `python -m uvicorn app.main:app`:
    - `GET /health` returned HTTP 200 with `{"status":"ok"}`.
    - `GET /measurements` returned 404.
    - The server listened only on `127.0.0.1:8000`.
- **Still pending:**
  - The CI workflow has no backend job yet, so these tests do not run in CI.
  - Not verified on macOS, on Linux, or with Python 3.11–3.13.
  - The known-vulnerability check (pip-audit) and linting (ruff) have not been run.
- **Human review:** None yet.

## 2026-11-14 · Member D · Claude Code · Backend CI job

- **Task:** Add a `backend` job to the CI workflow. On Linux, with Python 3.11 and 3.14, it installs `api/requirements-dev.txt`, runs the tests, and audits the installed dependencies with pip-audit.
- **Files changed:**
  - `.github/workflows/ci.yml` (new `backend` job)
  - `api/README.md` (CI and vulnerability notes)
  - `docs/AI_USAGE.md` (this entry)
- **New tool:** pip-audit 2.10.1 (Apache-2.0, maintained by PyPA). CI installs it for the audit step only. It is not an app dependency.
- **Local checks:** Run on Windows with Python 3.14.3.
  - First audit method, `python -m pip_audit -r requirements-dev.txt`: no known vulnerabilities in the 22 packages it listed (exit 0). That list left out `packaging`, which the test environment installs.
  - Cause of the gap, found from pip-audit's source and reproduced step by step:
    - In this mode, pip-audit first installs `wheel` in its own temporary environment, and `wheel` 0.48.0 requires `packaging`.
    - It then audits only the packages a dry-run install would still add. `packaging` was already present, so it was skipped without any warning.
  - Replacement method: save the installed list with `pip freeze`, then run `pip_audit -r <list> --no-deps --disable-pip`. It audited all 23 installed packages, including `packaging` 26.3: no known vulnerabilities, none skipped (exit 0).
  - Negative test: a throwaway requirements file pinning `requests==2.19.0`, checked with the same flags, made pip-audit exit 1.
  - `python -m pytest`: 10 passed, with 1 warning.
  - Text checks on the workflow file: no tabs, LF line endings, all 4 actions pinned to full commit SHAs, and no `|| true` or `continue-on-error`. The backend job uses `shell: bash`, so a failure anywhere in a pipe fails the step.
- **GitHub Actions result (first audit method):** the CI run on commit `4b8ed20` passed all three jobs.
  - The backend passed 10 tests each on CPython 3.11.18 and 3.14.10 (Linux, `ubuntu-26.04`).
  - That run used the first audit method, so it did not audit `packaging`.
- **Still pending:**
  - The replacement audit method has not yet run on GitHub Actions.
  - Python 3.12 and 3.13 are not in the test matrix.
  - pip, setuptools and wheel are not audited, because `pip freeze` leaves them out. They are install tools, not app dependencies.
  - Python linting (ruff) is not set up.
- **Human review:** None yet.

## 2026-11-14 · Member D · Claude Code · Hash-chained audit log

- **Task:** Add a hash-chained `records` table and a provisional `GET /audit/verify` endpoint. Member D chose the design: chain the records table itself, and add the endpoint now, marked provisional for A to confirm.
- **Files changed:**
  - `api/app/audit.py` (new)
  - `api/app/main.py` (new endpoint)
  - `api/tests/test_audit.py` (new)
  - `api/README.md`, `README.md` (audit-log notes and status)
  - `docs/AI_USAGE.md` (this entry)
- **No new dependencies:** the code uses only Python's standard library (`hashlib`, `json`, `sqlite3`).
- **Local checks:** Run on Windows with Python 3.14.3.
  - `python -m pytest`: 22 passed, with 1 warning (the existing Starlette deprecation notice). That is 12 new tests plus the 10 existing ones.
  - The new tests show that editing a stored field, deleting a middle record, or recomputing only the edited record's hash is detected.
  - Two tests document the known limits: rewriting every later hash, and deleting the last record, are not detected.
  - Live check with uvicorn and a scratch database holding 3 records:
    - `GET /audit/verify` first returned `{"valid":true,"records_checked":3}`.
    - After record 2's payload was edited directly in the file, it returned `{"valid":false,"first_broken_id":2,"reason":"record content does not match its stored hash"}`.
- **Correction to the previous entry:** the replacement pip-audit method did run on GitHub Actions. It ran on commit `ba102a3` (PR #7) and passed on Python 3.11.18 and 3.14.10, with `packaging==26.3` in the audited list.
- **Still pending:**
  - The response shape of `/audit/verify` needs A's confirmation.
  - The endpoint is open to any caller until demo access control exists.
  - The chain covers only records added through `append_record()`. Measurement writes are not connected to it yet; they wait for the G1 contracts.
  - Protection for the latest hash (an outside copy or a signature) is future work.
  - Concurrent appends have not been tested. When appends overlap, one can fail and must be handled, for example by retrying. No retry exists yet.
  - These tests have not yet run in CI.
- **Human review:** None yet.

## 2026-11-14 · Member D · Claude Code · Secret scanning (gitleaks)

- **Task:** Add a `secrets` job to the CI workflow. It scans the full Git history with gitleaks, and any finding fails the job. The existing frontend and backend jobs are unchanged.
- **Files changed:**
  - `.github/workflows/ci.yml` (new `secrets` job; the gitleaks line is removed from the "pending checks" comment)
  - `README.md` (secret-scanning status, and a note that a finding means the secret has already been pushed)
  - `docs/AI_USAGE.md` (this entry)
- **New tool:** gitleaks 8.30.1 (MIT), the official release from github.com/gitleaks/gitleaks.
  - CI downloads `gitleaks_8.30.1_linux_x64.tar.gz` and checks it against a pinned SHA-256.
  - That hash matched three sources: the release's `checksums.txt`, GitHub's asset digest, and a local hash of the downloaded file.
  - It is a CI tool only, not an app dependency.
- **Local checks:** Run on Windows with the gitleaks 8.30.1 Windows build, verified the same way.
  - **Our repository's history:** "no leaks found" (exit 0). It scanned 16 commits across all branches; the other 10 add no text. Those are 9 merge commits with empty combined diffs, plus `1a14c4f`, which only deletes files.
  - **Detection test in a throwaway local repository** (never in our shared repo):
    - A random value in the GitHub-token format (`ghp_` + 36 characters), in a file marked FAKE, was committed and then deleted in a later commit.
    - `gitleaks git` found it in history (rule `github-pat`, exit 1). `gitleaks dir`, which scans current files only, did not.
    - The value was redacted, and a check confirmed it never appeared in any output.
  - **Checksum step:** the pinned hash passed (exit 0); a hash with one character changed failed (exit 1).
- **Limits:**
  - Binary files are not scanned in Git-history mode: one `.xlsx` and one `.zip` in `download/` so far. The zip's contents are also committed as text files, which are scanned.
  - The job runs after a push, so anything it finds is already on GitHub. Removing it would need the credential revoked; history is not rewritten automatically.
- **CI correction to the previous entry:** the audit-chain tests have now run in CI.
  - On PR #9 (commit `a0fb961`), 22 of 22 tests passed on CPython 3.11.18 and 3.14.10.
  - The run on `main` after the merge (`a224417`) reported success; its logs were not inspected.
  - PR #9 was merged at 16:03 UTC, about 40 seconds after it opened. No human review is recorded.
- **Human review:** None yet.

## 2026-11-14 · Member D · Claude Code · OSD-575 dataset API (integration of A's engine)

- **Task:** Integrate Person A's approved engine commit `8475de9`, then add four read-only endpoints under `/datasets/osd575/`: astronauts, panels and biomarkers, measurement history, and postflight analysis. A approved the integration before any of A's files were merged.
- **Git:**
  - Branch `d-osd575-api`, created from `main` at `a81fcf1`.
  - The exact approved commit was merged with `git merge --no-ff` (merge commit `3d00b9c`). There was no cherry-pick or rebase, and nothing was merged into `main`.
  - `engine/` is byte-identical to `8475de9`.
  - A's later commit on `engine-main` (`bdd9fe0`, trajectory analysis) was **not** included, because it wasn't approved.
- **Files changed by D:**
  - `api/app/osd575.py` (new)
  - `api/app/main.py` (includes the router)
  - `api/pytest.ini` (adds the repository root to the import path)
  - `api/tests/test_osd575.py` (new)
  - `api/README.md` (new launch command and settings)
  - `docs/osd575-api.md` (new endpoint guide for Person C)
  - `docs/AI_USAGE.md` (this entry)
  - No file in `engine/` was changed.
- **Design:**
  - The API uses A's `load_osd575`, `group_measurements`, `analyze_postflight`, `serialize_measurement` and `serialize_analysis`. It does not repeat any calculation.
  - The data is loaded and analysed once per process, protected by a lock, and a failed load is not cached.
  - A missing CSV returns a 503 that names the file but no server path. Nothing is downloaded at runtime.
  - Responses add only an envelope (`study_id`, `provenance`, a "descriptive, not clinical" `note`, the request echo, and `count`). No risk levels or advice are added.
- **Local checks:** Run on Windows with Python 3.14.3.
  - A's engine tests (`python -m unittest discover -s engine`): 25 of 25 passed.
  - Backend tests (`python -m pytest`): 45 of 45 passed (22 existing, 23 new), with 1 warning (the existing Starlette deprecation notice).
  - C001 glucose at R+1: 90 mg/dL, baseline 77.33 and change +12.67 (within ±0.005), lab comparison `within`.
    - This was checked against the raw CSV (preflight values 83, 80 and 69), and against A's serializer output, which matched exactly.
  - Also tested:
    - Missing values (`null`, with status and raw text) and insufficient baselines.
    - Unknown or malformed crew IDs (404), unknown biomarkers (404) and unknown panels (422).
    - Strict JSON for all 4 crew members × 4 panels.
    - A missing data file (503).
    - Loading with the network blocked.
    - Loading once across many requests.
  - One test first failed for a test-design reason: on Windows, the test client's own event loop opens a local socket pair, which tripped the network block. The block now covers only loading and analysis.
  - Live check with uvicorn started from the repository root (`--app-dir api`):
    - All four endpoints returned 200.
    - The error cases returned the documented bodies.
    - With the data folder empty, the dataset endpoints returned 503 while `/health` still returned 200.
    - The examples in `docs/osd575-api.md` come from these responses.
- **Still pending:**
  - The response envelopes and error messages are provisional; A and C must confirm them, and the error format is TBD at G1.
  - Not yet run in CI or on Linux.
  - A's `unittest` suite is not in CI.
  - The launch command changed: the server must now be started from the repository root.
- **Human review:** None yet.

## 2026-11-14 · Member D · Claude Code · OSD-575 A3 trajectories, startup loading, CI for both suites

- **Task:**
  - Integrate Person A's approved A3 commit `bdd9fe0` (postflight trajectory analysis).
  - Add two read-only endpoints: one astronaut's trajectory, and a comparison of all four astronauts for one panel and biomarker.
  - Move dataset loading to application startup.
  - Make CI run both test suites.
- **Git:**
  - The finished A1/A2 API work was first committed as `aa5f9ca`.
  - The exact commit `bdd9fe0`, whose parent is the already-merged `8475de9`, was then merged with `git merge --no-ff` (merge commit `3a8a738`). No conflicts, no cherry-pick, no rebase, and nothing merged into `main`.
  - `engine/` is byte-identical to `bdd9fe0`.
- **Files changed by D:**
  - `api/app/osd575.py` (startup loading, two new routes)
  - `api/app/main.py` (lifespan)
  - `api/tests/test_osd575.py` (restructured and extended)
  - `.github/workflows/ci.yml` (engine unittest step)
  - `api/README.md`, `docs/osd575-api.md`, `docs/AI_USAGE.md` (this entry)
  - No file in `engine/` was changed.
- **Design:**
  - **New endpoints:** `GET /datasets/osd575/astronauts/{crew_id}/trajectory` and `GET /datasets/osd575/comparison`. Both require `panel` and `biomarker`.
  - **Reuse:** they use A's `analyze_trajectories`, `compare_astronauts` and `serialize_trajectory` unchanged. A `classification_note` states that closer, farther and mixed are not risk scores. The shapes are provisional until C confirms them.
  - **Startup loading:** a FastAPI lifespan loads the CSVs and precomputes A2 and A3 once per process. This replaces the first-request loading described in the A1/A2 entry above.
  - **Failure handling:**
    - Missing or unusable data is logged as an error.
    - The app still starts, `/health` stays a liveness check, and the dataset endpoints return 503 without server paths.
    - Fixing the data requires a restart.
  - **CI:** the backend job now runs `python -m unittest discover -s engine -v` from the repository root and `python -m pytest` from `api/`, on Python 3.11 and 3.14. The frontend and secret-scanning jobs are unchanged.
- **Local checks:** Run on Windows with Python 3.14.3.
  - Engine tests: 34 of 34 passed.
  - Backend tests: 69 of 69 passed (22 non-dataset, 47 dataset), with 1 warning (the existing Starlette deprecation notice).
  - The new tests cover:
    - the C001 glucose trajectory (values 90, 84, 91 and 87; classification `mixed`)
    - the four-astronaut glucose comparison (baselines 77.33, 73.00, 71.33 and 79.67)
    - equality with A's serializer output
    - missing observations as `null`, and insufficient baselines
    - required and unknown parameters
    - strict JSON for all 302 comparisons
    - a single load at startup and none per request, and 503 without startup
    - 503 and logging for missing and unreadable data
    - the restart requirement
    - loading with the network blocked
  - The C001 glucose acceptance test for R+1 is preserved and passes.
  - **Live server, started from the repository root:** both new endpoints returned 200, and the error cases returned the documented bodies.
    - With an empty data folder, `/health` returned 200 and the dataset endpoints 503.
    - Copying the CSVs into place while the server ran still gave 503, and a restart gave 200.
    - An earlier attempt at this check was invalid: a leftover server from a previous run was still on port 8000, because stopping the venv launcher process did not stop its child. It was found, stopped and the check redone.
- **Noted for A:** some A3 distance changes carry a 34-digit arithmetic remainder (C001 glucose `first_to_last_distance_change` = `-3.000000000000000000000000000000003`). It is reported, not changed.
- **Still pending:**
  - The response shapes are provisional until C confirms them, and the error format is TBD at G1.
  - Linux and Python 3.11 are verified only by CI.
- **Human review:** None yet. A requested a review of the integration PR.
