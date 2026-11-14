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

- **Task:** Add a `backend` job to the CI workflow. On Linux, with Python 3.11 and 3.14, it installs `api/requirements-dev.txt`, runs the tests, and audits the dependencies with pip-audit.
- **Files changed:**
  - `.github/workflows/ci.yml` (new `backend` job)
  - `api/README.md` (CI and vulnerability notes)
  - `docs/AI_USAGE.md` (this entry)
- **New tool:** pip-audit 2.10.1 (Apache-2.0, maintained by PyPA). CI installs it for the audit step only. It is not an app dependency.
- **Local checks:** Run on Windows with Python 3.14.3.
  - `python -m pip_audit -r requirements-dev.txt`: no known vulnerabilities in 22 resolved packages (exit 0).
  - Negative test: a throwaway requirements file pinning `requests==2.19.0`, checked without installing anything, made pip-audit exit 1.
  - `python -m pytest`: 10 passed, with 1 warning.
  - Text checks on the workflow file: no tabs, LF line endings, all 4 actions pinned to full commit SHAs, and no `|| true` or `continue-on-error`.
- **Still pending:**
  - The backend job has not run on GitHub Actions yet, so Linux and Python 3.11 are still unverified.
  - Python 3.12 and 3.13 are not in the test matrix.
  - Python linting (ruff) is not set up.
- **Human review:** None yet.
