# AI usage log

The event requires a description of how AI tools were used. Every agent session gets an entry here with at least the date, member, tool, task, files changed and human review status. Add new entries at the bottom and keep earlier entries unchanged.

Team members: A = Iliass Barrou, B = Ayman El Kerboubi, C = Taha Errassif, D = Monssif El Haouari. The entries below use these letters.

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

## 2026-11-14 · Member D · Claude Code · 3D astronaut fixes and new model (frontend/, with C's approval)

- **Task:** Fix two frontend bugs found while reviewing C's commit `e471f37`, and replace the hand-drawn astronaut with the Sketchfab model D chose. D reported that C approved these edits in `frontend/`.
- **Branch:** `d-astronaut-fixes`, built on C's branch `c-osd575-demo-fixes` (`e471f37`).
- **Files changed:**
  - `frontend/src/components/Astronaut3D.tsx` (crash fix, then rewritten as a three.js viewer)
  - `frontend/src/pages/Dashboard.tsx` (hidden-demo fix)
  - `frontend/package.json` and `frontend/package-lock.json` (three.js)
  - `frontend/public/models/astronaut/` (model and textures, new)
  - `frontend/public/licenses/Astronaut-model-NOTICE.txt` (new)
  - `docs/AI_USAGE.md` (this entry)
- **Fixes:**
  - **Drag crash:** dragging the 3D astronaut could unmount the whole app. Pointer-move state updates read a ref that pointer-up had already set to null. This was reproduced every time before the fix and never after it.
  - **Hidden demo:** the guided demo kept running while the dashboard was hidden, and Escape could not stop it from NASA. It now stops when the workspace is hidden.
- **New model:**
  - "Astronaut" by Javi_DaviYT (Sketchfab), CC BY 4.0, downloaded by D. The original creator is unverified: the page says "Cool astronaut I found!".
  - The FBX is used unmodified. Four textures were downscaled from 4096 px to 1024 px, cutting the files from 80 MB to 6.1 MB. The displacement map is not included.
  - The files are served from the app, so it works offline.
  - three.js 0.187.0 (MIT) and @types/three 0.187.0 (MIT) are pinned to exact versions, with 0 vulnerabilities from npm audit. The JavaScript bundle grew by about 154 KB gzipped.
  - The viewer shows the required attribution, and a clear message if the model or WebGL is unavailable.
- **Local checks:** Windows, Node 24, production build served by `vite preview` with the local backend.
  - The build passes, with Vite's warning about bundles over 500 KB.
  - The model loads from the local server only, with no external requests.
  - It renders upright and facing front, framed with space around it.
  - Drag, arrow keys, zoom and reset work.
  - Arrow keys on the 3D view no longer move the dashboard's visit.
  - Five rapid drags cause no errors.
  - There are no console errors or warnings.
  - NASA regression: C001 glucose R+1 still shows 90 mg/dL, 77.33, +12.67 and within, and the C003 `activin_a` L-44 gap is unchanged.
- **Still pending:** the rendering has not been checked on other browsers or on a phone.
- **Human review:** None yet. C's review is requested on the PR.

## 2026-11-14 · Member D · Claude Code · Sidebar navigation, shared heading and one palette (frontend/, with C's approval)

- **Task:** D asked for a left sidebar that splits the one long page into separate pages, the same heading on every page, and the "Check-in & body" colour palette on every page. D reported that C approved these edits in `frontend/`. Every existing feature stays; only where it appears changes.
- **Branch:** `d-sidebar-layout`, from `main` at `2169c23`.
- **Files changed:**
  - `frontend/src/components/Sidebar.tsx` and `frontend/src/components/PageHeader.tsx` (new)
  - `frontend/src/App.tsx` (sidebar layout instead of the two top buttons)
  - `frontend/src/pages/Dashboard.tsx` (split into a check-in section and a body section)
  - `frontend/src/components/TopBar.tsx` (brand and badge moved out)
  - `frontend/src/pages/NasaDataset.tsx` (own heading removed, chart colours)
  - `frontend/src/index.css` (sidebar styles, and the NASA styles redone in the check-in palette)
  - `docs/AI_USAGE.md` (this entry)
- **Design:**
  - **Three pages:** NASA lab data (still the first page), Daily check-in, and Body & systems (3D astronaut, system cards, visits and the system detail).
  - **Shared heading:** every page uses the same heading layout. Its badge says SIMULATED DATA on the two prototype pages and RECORDED DATA · OSD-575 on the NASA page, so recorded data is never labelled as simulated.
  - **State kept:** pages are hidden, not removed, so check-in drafts and the loaded 3D model survive page changes.
  - **Guided demo:** the demo, its button and the arrow-key and D shortcuts now belong to the Body & systems page. The demo stops when that page is hidden.
  - **Icons and accents (D's follow-up request):**
    - Each page has a simple line icon drawn for this app; no icon library was added.
    - Each page also has its own accent colour, used for icons, the heading, panel labels and hover glows: sky blue for NASA, mint for check-in, lavender for body.
    - Accents stay apart from status colours. The check-in page shows no statuses. The body page, which shows green, amber and red statuses, uses lavender.
    - Pages fade in when opened. Users who turn off animations in their system settings get no motion.
- **Local checks:** Windows, Node 24, Vite dev server with the local backend.
  - The production build passes, with Vite's existing warning about bundles over 500 KB.
  - At 1440, 1100 and 375 px wide, each page shows the right sections with no sideways scrolling. The sidebar moves to the top on narrow screens.
  - A check-in value survives switching pages. Arrow keys change the visit on the body page only. The demo stops when you leave that page. The 3D model is still drawn when you come back.
  - NASA regression: C001 glucose R+1 still shows 90 mg/dL.
  - **Correction to the previous entry:** the console is not free of warnings. three.js's FBX loader prints three warnings every time the astronaut model loads (two unsupported texture types are skipped, and extra skinning weights are dropped). This has been true since the model was added. No errors appear.
- **Still pending:** not checked on other browsers or on a real phone.
- **Human review:** None yet. C's review is needed before merging.

## 2026-11-14 · Member D · Claude Code · Mode 1 assessment API and A4 passport endpoint

- **Task:** integrate A's `engine-main` (A4 commit `bf284ce`) into the backend. Connect Mode 1 M2 statistical detection to FastAPI, add a read-only A4 passport endpoint, and write the integration guide for C. Requested in the team's integration brief, which D pasted.
- **Branch:** `d-mode1-passport-api`, from `main` at `4871160`. A's four engine commits were merged with a merge commit, unchanged: `engine/` equals `bf284ce`, and no engine file was edited.
- **Files changed:**
  - `api/app/monitoring.py` (new)
  - `api/app/main.py`, `api/app/osd575.py`
  - `api/tests/test_monitoring.py` and `api/tests/test_passport.py` (new)
  - `api/README.md`
  - `docs/mode1-api.md` (new guide for C)
  - `docs/examples/mode1/` (real examples generated from the API)
  - `docs/AI_USAGE.md` (this entry)
- **Design:**
  - **Startup:** B's synthetic history is loaded once and indexed with A's `HistoryIndex`. A load failure gives 503 without server paths.
  - **Assessment:** `POST /api/monitoring/assess` validates the request with `validate_manual_check_in()` (failures give 422) and returns `assess_check_in()` unchanged. That function validates its own output.
  - **Unknown crew:** an unknown astronaut ID gives 422 instead of a silent `insufficient_data`.
  - **M3 is never imported:** the M3 Isolation Forest stays off.
  - **Passport:** `GET /datasets/osd575/astronauts/{crew_id}/passport?visit=` reuses the A2 and A3 results cached at startup.
- **Local checks:** Windows, Python 3.14.3.
  - Backend: 108 passed (69 existing and 39 new), 1 known warning.
  - Engine: 73 run, 68 passed, 5 skipped (M3 tests need the optional scikit-learn, which is not installed).
  - C002 R+45 passport equals A's example file exactly.
  - Mode 1 tests cover:
    - normal, unusual (`chest`) and insufficient-data results;
    - only strictly earlier readings counting;
    - rest and exercise history never mixed;
    - the `other` context;
    - invalid input and unknown astronauts;
    - exact decimal digits;
    - M3 not loaded;
    - loading once;
    - 503 without paths;
    - loading and assessment with the network blocked.
  - A live server on port 8010 returned the same results.
- **Open points (in `docs/mode1-api.md`):**
  - The contract accepts only `data_origin: "user"`, so simulated demo entries can't be marked (A).
  - The engine's body systems don't match the frontend's system cards (A and C).
  - The Vite proxy needs `/api` (C).
  - Endpoint names are proposed.
  - Check-ins are not stored or chained.
- **Human review:** None yet. A's and C's review is requested on the PR.

## 2026-11-14 · Member D · Claude Code · Frontend connected to the Mode 1 and A4 APIs (frontend/, with permission)

- **Task:** C's frontend integration brief, done by D. D reported that A, B and C gave permission. The goal: connect the existing prototype to the real engine through D's API, without redesigning it.
- **Branch:** `d-frontend-engine`, built on the backend branch `d-mode1-passport-api` (PR #20), so the endpoints exist.
- **Mode 1:**
  - **Check-in form:** sends the exact `MODE1_CONTRACT.md` request (decimal strings, units, UTC timestamp, `data_origin: user`) to `POST /api/monitoring/assess`. The form gained crew, context, mission time and respiratory rate, and lost temperature.
  - **Crew and defaults:** the crew list and the default time after the history come from `GET /api/monitoring/astronauts`.
  - **No calculations in React:** statuses map to colours for display only. Green means normal, amber means unusual, grey means not assessed, and red is kept for an approved rule.
  - **Astronaut:** shows a clickable marker only where `body_marker` says.
  - **Evidence panel:** shows the backend's evidence, findings, limitations and "no approved action protocol" text.
  - **Removed (mock only):** the mock fixtures, the NASA-visit timeline and the guided demo.
- **Mode 2:**
  - **Passport:** the NASA page shows the A4 passport (`GET /datasets/osd575/astronauts/{crew}/passport?visit=`). It shows counts, panels, findings, the later-observations note, limitations and sources. Lab "unavailable" is labelled as not a missing reading.
  - **Chart link:** each finding's "Chart" button drives the existing A1–A3 chart.
- **Configuration:** a configurable `VITE_API_BASE_URL` (default: same origin), and `/api` added to the Vite proxy. No CORS.
- **End-to-end checks:** Windows, dev server proxied to a local API.
  - Normal: green, no marker.
  - Unusual: amber chest marker. Clicking the 3D marker opens heart-rate evidence: 85 vs 66.5 bpm, z 12.47825.
  - Insufficient: grey, with reasons.
  - Errors: 422 and backend-down messages, and the loading state, show clearly.
  - C002 R+45 passport: 302 biomarkers, 1 below the lab interval, 284 with no lab comparison. The request is sent with `%2B`.
  - All 59 page requests were local, and the console shows no errors.
  - `npm run build` passes.
  - Screenshots are in `docs/screenshots/frontend-e2e/`.
- **Not done:**
  - Mode 1 history charts: the API exposes no per-reading history yet. It needs a public helper from A, or a new endpoint from D.
  - C's mock-only files are now unused but not deleted.
- **Human review:** None yet.

## 2026-11-15 · Member D · Claude Code · Repository structure cleanup

- **Task:** D asked for a clean repository: no duplicate or dead files, no outdated READMEs, and a tidy branch list. D reported permission from A, B and C, and approved each removal and the branch deletions.
- **Branches:**
  - #21 (frontend) had been merged into its base branch after that base was already merged into `main`, so `main` lacked the frontend. PR #22 brings commit `c6762b2` to `main`.
  - 13 remote branches fully merged into `main` were deleted, each checked with `git merge-base --is-ancestor` first.
  - Kept: `main`, `engine-main` (A's working branch), `data` (B's unmerged work), and the two branches of #22 until it merges.
- **Branch `d-repo-cleanup`, in four commits:**
  1. **Removed:**
     - the duplicate metadata `.zip` (byte-identical to the unzipped folder) and 5 empty `.gitkeep` files;
     - frontend files nothing imports: the mock loader and its 4.9 MB fixture, the old SystemDetail, TrendChart and DatasetComparison, the unreachable muscle map with its data, licence files and CSS, and an unused SVG;
     - `frontend/PLAN-CHECKPOINTS.md`.
  2. **Fonts:** the 4 Inter weights moved from base64 in `index.css` (1.78 MB, now 47 KB) to font files, with the official OFL 1.1 licence from the Inter project's v4.0 release.
  3. **Ignore rules and settings:**
     - A focused `.gitignore` replaces the Python template; it ignores the same local files before and after.
     - The duplicate `frontend/.gitignore` was removed.
     - New `.env.example` and `frontend/.env.example`.
  4. **Docs:**
     - The root README is rewritten to match what is built.
     - New READMEs for `frontend/` and `download/`.
     - An overview table in `engine/README.md`.
     - Passport row in `docs/osd575-api.md`, and updated open points in `docs/mode1-api.md`.
     - `AGENTS.md`/`CLAUDE.md` now show the real folders, check commands and interfaces (both still identical).
- **Checks (local, Windows):**
  - Engine: 73 tests run, 5 skipped (M3 needs scikit-learn).
  - Backend: 108 passed.
  - `npm run build` passes.
  - In the production build, the 4 Inter fonts load (HTTP 200) and the served licence notices open.
  - Every relative link in the changed docs resolves.
- **Not changed:**
  - The data folders' paths (D chose to keep them).
  - The rules themselves in `AGENTS.md`.
  - B's `data` branch.
  - The missing repository licence, which is a team decision.
- **Human review:** None yet.

## 2026-11-15 · Member D · Claude Code · Project licence (Apache 2.0) and NOTICE

- **Task:** choose the best licence for the competition and add it. D asked for this after the branch cleanup.
- **Research:**
  - The challenge page says nothing about licences.
  - The [2026 Participant Terms and Conditions](https://www.spaceappschallenge.org/legal/) say original content must be freely available or under an OSI open-source licence, and "If you do not specify a specific OSI compliant license, NASA will distribute your original content under an Apache 2.0 license".
  - Third-party materials need their licences documented, and every source must be cited.
- **Branch `d-license-apache`:**
  - `LICENSE`: the official Apache 2.0 text from apache.org (SHA-256 `cfc7749b…`).
  - `NOTICE` (new): project copyright, plus every third-party item with its licence: OSD-575 data, the NASA sources behind the synthetic data, the Inter font, the 3D model, and the npm and pip dependencies.
  - README licence note.
  - The dependency licences were read from the installed packages: all MIT, BSD-3-Clause or Apache-2.0.
- **Same session:** #22 and #23 were already merged, and CI passed on `main`. Deleted branches `d-frontend-engine`, `d-mode1-passport-api`, `d-repo-cleanup` and `data`. Every file on `data` was byte-identical to a file on `main` except one unused Mars radiation CSV, which GitHub still keeps through closed PR #18.
- **Open:**
  - The 3D model's original creator is unverified, and the Space Apps terms exclude material the team has no rights to.
  - The OSD-575 terms of use still need B's check.
- **Human review:** None yet.

## 2026-11-15 · Member D · Claude Code · R1 radiation history API (Mission Environment)

- **Task:** the R1 backend brief: serve Iliass Barrou's radiation history engine through FastAPI without changing Mode 1 or Mode 2. Monssif El Haouari reported permission from the whole team.
- **Branch:** `d-radiation-api`, from `main` at `49c0f69`.
- **Engine:** Iliass's `engine-main` commit `56875db` was merged unchanged; its 3 radiation files are byte-identical.
- **Data:**
  - Iliass had already committed the CSV to `main` at the engine's default path, so no second copy was added.
  - Its data is identical to Ayman El Kerboubi's export (closed PR #18) and to the file Monssif supplied.
  - The file is now stored byte-for-byte (`.gitattributes` `-text`), so the SHA-256 the API reports is `d514a88f…` on every computer, as in `engine/RADIATION_HISTORY.md`.
  - A README was added for the data folder.
- **API (`api/app/radiation.py`):**
  - Loads the CSV once at startup, with the path passed explicitly (`CREW_HEALTH_RAD_CSV` overrides it).
  - `GET /api/environment/radiation/timeline` and `GET /api/environment/radiation/events/may-20-2024` return the engine's dictionaries unchanged.
  - Errors: 422 for bad dates, 404 for an unknown detector, 503 without server paths when the CSV is missing or unreadable.
- **Docs:**
  - New `docs/radiation-api.md` for Taha Errassif, with real example responses in `docs/examples/radiation/`.
  - Updated: the API README, `.env.example`, the root README, NOTICE (dataset citation), the engine README table, and `AGENTS.md`/`CLAUDE.md` section 4.
- **Checks (local, Windows):**
  - Backend: 126 passed (108 existing, 18 new).
  - Engine: 78 run, OK, 5 skipped (M3 needs scikit-learn). Iliass's real-data radiation test ran.
  - Values match the brief: May 20 peak 8377.913 µGy/day at 06:15:19 UTC, median 1153.6759, May 13–19 median 148.34653, ratio 7.7768.
- **Human review:** None yet.

## 2026-11-15 · Member D · Claude Code · Mission Environment tab (Mars Radiation History)

- **Task:** the frontend R1 brief: add a third, separate area for the Mars radiation history in the existing theme and navigation, connected to the radiation API (#26). Mode 1 and Mode 2 are not changed. Monssif El Haouari reported permission from the whole team, including Taha Errassif for `frontend/`.
- **Branch:** `d-radiation-tab`, from `main` after #26.
- **Files:**
  - New: `frontend/src/pages/RadiationHistory.tsx`, `components/RadiationChart.tsx`, `services/radiation.ts`.
  - Edited: `App.tsx`, `components/Sidebar.tsx` (fourth item and icon), `components/PageHeader.tsx` (each page's badge text), `index.css`.
  - Docs: README, frontend README, two screenshots.
  - No new dependency.
- **Chart (SVG):**
  - Detector E readings from the API on a UTC time axis, in µGy/day labelled as a rate.
  - Line breaks and shaded bands where readings are more than 3 hours apart; nothing is interpolated.
  - The May 20 band, the API's peak marker, and an "export ends" marker so the event does not look finished.
  - Hover tooltips with time, value and unit; drag to zoom with Reset; date-range presets taken from the event response, plus custom dates sent to the API; an optional log scale.
  - The event card reads every number from the event endpoint.
- **Checks (local, Windows; dev server proxied to the API):**
  - 5,971 readings, 10 gaps, May 20 band, peak and end marker drawn.
  - The event card shows 8,377.913 µGy/day at 06:15:19 UTC, median 1,153.6759, May 13–19 median 148.34653, 7.78×.
  - The event-week preset requests the dates from the API (718 readings).
  - Hover, drag-zoom and log scale work.
  - A start after the end shows the API's 422 inside the tab; a simulated 503 shows an unavailable state while Mode 1 keeps working, and Retry recovers.
  - Mode 1 (unusual example, chest marker) and Mode 2 (C002 R+45 passport, 302 biomarkers) are unchanged.
  - All 70 requests local; no horizontal overflow at 375 px.
  - `npm run build` passes.
- **Human review:** None yet.

## 2026-11-15 · Member D · Claude Code · Final cleanup and full check after R1

- **Branches:** after #26 and #27 merged, `engine-main` had no commit missing from `main`; its tip `56875db` is part of `main`. It was deleted, leaving `main` as the only branch, and the PR branches were removed automatically.
- **Docs:** `engine/RADIATION_HISTORY.md` corrected two stale facts: the CSV is committed (no longer only on the deleted `data` branch), and the real routes replace the proposed ones.
- **Audit of `main`:**
  - The only duplicate files are `AGENTS.md`/`CLAUDE.md` (intentional).
  - No tracked file matches the ignore rules.
  - All 18 Markdown files have 0 broken relative links.
- **Fresh-clone check:**
  - `main` (`ad53f71`) was cloned from GitHub; its CSV hash was `d514a88f…`.
  - The API was started with outbound networking disabled (loopback only). All three datasets loaded, and every mode answered:
    - radiation 5,971 readings, peak 8377.913 at 06:15:19;
    - Mode 1 unusual, chest;
    - Mode 2 passport 302, glucose 90, +12.67, within.
  - The frontend was installed with `npm ci` and built. All four tabs worked in the browser on real data, with 22 requests, all local, and no console errors.
- **Human review:** None yet.

## 2026-11-15 · Member D · Claude Code · One data/ folder for the three datasets

- **Change:** the three dataset folders now sit in one top-level `data/` folder, with one subfolder per part of the app:
  - `iss-synthetic-3000/` → `data/mode1/` (synthetic history, Mode 1);
  - `download/` → `data/mode2/` (NASA OSD-575, Mode 2);
  - `raw data/NASA Curiosity radiation/` → `data/radiation/` (Mission Environment).
- **Approval:** D's request. D confirmed that Ayman El Kerboubi (B, data owner) and Iliass Barrou (A, engine owner) agreed. D's first message mapped the two Mode folders the other way round; D chose the mapping that matches what the code reads.
- **Files:**
  - every data file is a pure Git rename, with no content change; the radiation CSV keeps SHA-256 `d514a88f…`;
  - the three default paths in `engine/` (one line each);
  - the API's docstrings and 503 messages;
  - `.gitattributes`, `.env.example`, the READMEs, `NOTICE`, the guides, and `AGENTS.md`/`CLAUDE.md` (B owns `data/`; the `download/` proposal is settled);
  - new `data/README.md`, which says which dataset feeds which part of the app.
- **Not changed:** the dataset name `iss-synthetic-3000` (still used for B's ZIP and the M3 dataset version), the environment variable names, and older entries in this log, which describe paths as they were then.
- **Checks (local, Windows):**
  - Engine: 78 tests, OK, the same 5 skipped (optional scikit-learn) as before the move, with identical per-test results.
  - API: 126 passed, as before.
  - `npm run build` passes.
  - No tracked file still names an old path, except older log entries and the dataset name; all 59 relative links in the 19 Markdown files resolve.
- **Fresh-clone check:** the branch was cloned into a new folder. `git status` was clean, the radiation CSV hash was `d514a88f…`, and no old folder remained.
  - The API was started with outbound networking disabled (loopback only). All three datasets loaded: radiation 5,971 readings, peak 8377.913 at 06:15:19; Mode 1 example unusual, chest; Mode 2 passport C001 R+45, 200.
  - 30 Mode 1 and Mode 2 responses were byte-identical to an API still running the old folder layout.
  - All four tabs worked in the browser against it, with no console errors.
- **Human review:** None yet.

## 2026-11-15 · Member D · Claude Code · Playwright bug hunt, fixes and check-in checks

- **Testing:** Playwright 1.64.1 (Apache-2.0, 0 known vulnerabilities) was installed outside the repository and drove Microsoft Edge against a local copy of the app with outbound networking disabled. It covered 50 browser scenarios, 70 malformed API requests, every Mode 2 biomarker (3,926 responses and 16 passports) and 4 time zones. No dependency was added to the project.
- **Bugs fixed:**
  - `api/app/monitoring.py`: JSON nested about 20,000 levels deep raised an uncaught `RecursionError` (500 and a long traceback in the log). It now returns 422.
  - `frontend/src/components/RadiationChart.tsx`:
    - On a phone the chart's labels shrank to about 4 px. The drawing now follows the chart's real width (320–960 px), so labels keep their 11 px size, and narrow charts show fewer, shorter time labels.
    - When the visible range started on 20 May, the "solar event" label was drawn off the chart's left edge. It now moves inside the event band.
  - `frontend/src/components/DailyCheckIn.tsx`: number boxes accepted `1e3`, which the evidence panel showed as "1E+3 bpm". The form now accepts plain decimals only.
  - `frontend/public/favicon.svg` and `index.html`: the missing icon caused a 404 on every page load. The icon reuses the sidebar's compass logo.
- **Check-in checks (D's choice: logic checks only):**
  - New `api/app/checkin_checks.py`. After A's validator, the API rejects readings that cannot be real by definition: numbers that are not plain decimals (up to 4 digits before the point and 3 after), a rate or pressure of 0, systolic not above diastolic, and more than 24 h of sleep. The form applies the same rules.
  - These are not medical limits. Physiological ranges still need a cited source from B, so 300 bpm is still assessed (a test records this).
- **Security note:** `POST /api/monitoring/assess` now requires `Content-Type: application/json` (otherwise 415). Another website can send a `text/plain` or form POST through a visitor's browser without a CORS preflight; a JSON POST cannot. This matters once check-ins are stored.
- **Docs:** `docs/mode1-api.md` (checks, 415), `docs/examples/mode1/errors.json` (real 415 and 422 responses), `api/README.md` and `AGENTS.md`/`CLAUDE.md` (errors, still-open items).
- **Approval:** D asked for the fixes, chose logic checks only, and confirmed that Iliass Barrou (A) approved this contract change.
- **Checks:**
  - pytest: 151 passed (126 before, plus 25 new). Engine: 78 tests OK, 5 skipped.
  - `npm run build` passes.
  - Re-run of the Playwright suite: 50/50, no favicon 404.
  - API re-test: 415 for `text/plain`, 422 for every impossible reading and for deep JSON, and no 500 in the log.
- **Not changed:** timestamps far outside the mission calendar (for example the year 9999) are still accepted; that would also need a team rule.
- **Human review:** None yet.
