# Crew Health Compass

An offline-first health-monitoring prototype for astronauts on long missions, built for the **NASA Space Apps Challenge 2026**: *Create Health Monitoring Software for Astronauts on Space Missions*.

> **Hackathon prototype.** This is not a medical device. It is not clinically validated and does not comply with any health-data regulation. Synthetic data is labelled **SIMULATED**; real data names its source (NASA OSD-575).

## What it does

The app has two clearly separated modes, plus a historical Mission Environment tab.

| Mode | Data | What you can do |
|---|---|---|
| **Mode 1: Mission Health Monitor** | Synthetic ISS history: 4 fictional crew members, 3,000 readings (`iss-synthetic-3000/`) | Enter a daily check-in (heart rate, respiratory rate, blood pressure, optional sleep and mood). The backend compares it with the same astronaut's earlier readings in the same activity context. The 3D astronaut shows the result, and the evidence panel shows the numbers behind it. |
| **Mode 2: NASA Biological Passport** | Real NASA study OSD-575: blood serum panels of the 4 Inspiration4 crew members (`download/`) | Pick a crew member and a postflight visit, and see each biomarker compared with that person's own preflight average and the supplied laboratory limits, plus trajectories across all visits. |
| **Mission Environment: Mars Radiation History** | Real NASA Curiosity RAD measurements on the Martian surface: 5,971 dose rates, 7 March–20 May 2024 (`raw data/NASA Curiosity radiation/`) | Explore the radiation timeline (zoom, date range, hover), and the 20 May 2024 solar event compared with the week before. It describes the Mars environment only and never changes a health status. |

Mode 1 statuses are **green** (no unusual pattern among the compared readings), **amber** (a statistical difference from personal history) or **grey** (not assessed: unknown, not normal). Red is reserved for an approved medical rule, and none exists yet. No treatment advice is shown.

Mode 2 is descriptive. It is not a validation of the Mode 1 detector.

A message between Mars and Earth takes 4–24 minutes one way. For that reason, everything runs offline: every dataset is read from local files, and no external AI service is called.

## How it works

```
frontend/ (React)  ──►  api/ (FastAPI, the trust boundary)  ──►  engine/ (Python standard library)
   check-in form           validates input, loads data once        Mode 1: M2 personal robust statistics
   3D astronaut            at startup, returns engine output       Mode 2: A1–A4 OSD-575 analyses
   NASA passport           unchanged
```

1. The browser sends a check-in to `POST /api/monitoring/assess`. In development, Vite's proxy forwards it to the API on the same origin.
2. The API validates it with Iliass Barrou's contract (`validate_manual_check_in`). Invalid input gets HTTP 422.
3. Iliass Barrou's engine compares it with the latest 14 earlier readings of the same astronaut, context and measurement protocol (median and MAD, robust z-score). It never mixes rest and exercise readings.
4. The UI shows the backend's `overall_status`, `body_marker` and `evidence` without recalculating anything.
5. Mode 2 reads the A1–A4 results, which the API computes once at startup.

The API also keeps a **hash-chained audit log** (`GET /audit/verify`). Check-ins are not stored in it yet.

## Repository layout

| Path | Contents | Owner |
|---|---|---|
| `engine/` | Analytics: OSD-575 ingestion and analyses (A1–A4), Mode 1 contracts and detection, guides and JSON examples | Iliass Barrou |
| `iss-synthetic-3000/` | Synthetic ISS dataset for Mode 1 (see its README) | Ayman El Kerboubi |
| `download/` | NASA OSD-575 files: the source data for Mode 2 (see its README) | Ayman El Kerboubi (*proposal*) |
| `raw data/NASA Curiosity radiation/` | Curiosity RAD radiation CSV for the Mission Environment tab (see its README) | Ayman El Kerboubi |
| `frontend/` | React + Vite + TypeScript user interface | Taha Errassif |
| `api/` | FastAPI app: Mode 1 and Mode 2 endpoints, SQLite audit log, tests | Monssif El Haouari |
| `docs/` | API guides for the frontend, JSON examples, screenshots, AI-usage log | Monssif El Haouari (*proposal*) |
| `.github/workflows/` | CI: frontend build and audit, backend and engine tests, dependency audit, secret scan | Monssif El Haouari |

## Run it locally

You need Python 3.11 or newer and Node.js. The commands are for Windows PowerShell, from the repository root.

**Backend** (first time only: create the environment and install):

```powershell
python -m venv api\.venv
api\.venv\Scripts\python.exe -m pip install -r api\requirements-dev.txt
api\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir api
```

**Frontend**, in a second window (`npm ci` again after every pull that changes `package-lock.json`):

```powershell
cd frontend
npm ci
npm run dev
```

Open the address Vite prints, usually `http://localhost:5173`. The settings and their defaults are in [`.env.example`](.env.example) and [`frontend/.env.example`](frontend/.env.example).

**Tests:**

```powershell
api\.venv\Scripts\python.exe -m unittest discover -s engine
cd api; .venv\Scripts\python.exe -m pytest; cd ..
cd frontend; npm run build; cd ..
```

## Documentation

| Guide | For |
|---|---|
| [api/README.md](api/README.md) | Backend setup, configuration, audit log, dependencies |
| [docs/mode1-api.md](docs/mode1-api.md) | Mode 1 endpoints, request format, errors, A4 passport |
| [docs/osd575-api.md](docs/osd575-api.md) | Mode 2 OSD-575 endpoints in detail |
| [docs/radiation-api.md](docs/radiation-api.md) | Mission Environment radiation endpoints, fields and errors |
| [engine/README.md](engine/README.md) | Engine overview and the A1–A3 analyses; links to the Mode 1 and A4 guides |
| [frontend/README.md](frontend/README.md) | Frontend structure, settings and checks |
| [iss-synthetic-3000/README.md](iss-synthetic-3000/README.md) | How the synthetic dataset was built |
| [download/README.md](download/README.md) | What the NASA files are and which ones the engine reads |
| [docs/AI_USAGE.md](docs/AI_USAGE.md) | Log of every AI-assisted change |

## Data and provenance

Every record says where it came from: `user` (entered in the app), `simulated`/`synthetic` (generated), or `dataset:OSD-575` (NASA). The UI labels synthetic data **SIMULATED** and names the NASA study on Mode 2 pages.

### NASA OSD-575 (`download/`)

| What the files state | Evidence in the repository |
|---|---|
| NASA Open Science Data Repository study OSD-575: "SpaceX Inspiration4 Blood Serum Metabolic Panel and Immune/Cardiac Cytokine Arrays" | `i_Investigation.txt`: `Study Identifier`, `Study Title` |
| Inspiration4 mission, 16–18 September 2021, "four private astronauts"; public release 14 May 2024 | `i_Investigation.txt`: `Comment[Mission Name]`, `Comment[Mission Start]`, `Comment[Mission End]`, `Study Description`, `Study Public Release Date` |
| Four subjects with coded IDs C001–C004 | `SUBJECT_ID` column of `LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv`; `Source Name` in `s_OSD-575.txt` |
| Samples before launch (L-92, L-44, L-3) and after return (R+1, R+45, R+82, R+194) | `timepoint` column of the metabolic panel `_SUBMITTED.csv`; `Factor Value[Time]` in `s_OSD-575.txt` |
| Blood tests, not daily vitals: a 19-analyte metabolic panel plus immune and cardiac cytokine panels | `ANALYTE` column of the metabolic panel `_SUBMITTED.csv`; `Type` column of the Eve Panel `_SUBMITTED.csv` files |

The metadata files are in `download/OSD-575_metadata_OSD-575-ISA/`.

**Not yet checked (for Ayman El Kerboubi):** the OSDR web page itself, the data licence and terms of use, and whether these files exactly match the official download.

**Open question for the team:** the Inspiration4 crew is publicly known, so coded IDs plus recorded sex may not keep individuals anonymous. The team should decide before this data appears in a public demo.

### Synthetic ISS history (`iss-synthetic-3000/`)

These are fictional crew roles (`commander`, `flight_engineer_1`–`3`) on a simulated 2030 mission calendar. Each file keeps the column format of a historical NASA table (Apollo 10, Apollo–Soyuz, Skylab 4), but every value is generated. The method and sources are in its [README](iss-synthetic-3000/README.md).

### Curiosity radiation history (`raw data/NASA Curiosity radiation/`)

These are real NASA measurements: 5,971 absorbed dose **rates** (µGy/day) recorded by the Radiation Assessment Detector on the Curiosity rover, on the Martian surface, from 7 March to 20 May 2024. The period includes NASA's documented solar event on 20 May 2024. They describe the Mars environment, not any astronaut's exposure, and they never feed the health assessment. Details are in its [README](raw%20data/NASA%20Curiosity%20radiation/README.md).

## Security and data integrity

The scope is kept small enough for a hackathon. Each protection has been tested only on our local prototype.

| Protection | What it does | Status |
|---|---|---|
| Input validation | Mode 1 check-ins are validated with Iliass Barrou's contract at the API. Malformed values, unknown units, unknown crew IDs and non-JSON bodies are refused with HTTP 422 and a message. | Built and tested locally |
| Plausibility checks | Physically impossible values become a "data problem, re-measure" result instead of a finding | Planned |
| Offline operation | All three datasets load from local files at startup. Tests block network access during loading and assessment. | Built and tested locally |
| Hash-chained audit log | `GET /audit/verify` names the first stored record that no longer matches its fingerprint | Built and tested locally. No check-ins are stored in it yet, and the response shape is provisional |
| Secret and dependency scanning | CI runs npm audit, pip-audit and a gitleaks scan of the full Git history on every PR into `main` and every push to `main`. Binary files are not scanned for secrets. | Running in CI |
| Demo access control | A fixed demo token per role (astronaut or flight surgeon): basic **authentication** (identifying the caller through the token) and **authorization** (checking what that caller may access) | Planned |
| Encryption at rest | Measurement values encrypted inside the SQLite file | Planned |
| Signed report packet | Ed25519 signature; changing one byte makes verification fail | Planned, if time permits |

Each protection stays **Planned** until it is implemented and tested.

**Known limits:**

- Demo access control is **not** production-ready account management. There are no user accounts and no passwords, and the tokens are fixed demo values. Anyone who has a token can act as that caller. A token that is shared or publicly exposed does not establish a private user identity.
- The hash chain detects edits to stored records, but it has two blind spots:
  - Someone who can write to the database file can change a record and recompute every later hash, because the hash uses no secret key.
  - Deleting records from the end leaves a valid, shorter chain.
- Mode 1 thresholds are exploratory statistics on synthetic history, not medical limits.
- `.gitignore` is not a guarantee:
  - it has no effect on a file that is already tracked
  - `git add -f` overrides it
  - it cannot see a secret pasted into an ordinary file

  Everyone checks their own diff before committing. The gitleaks scan in CI is the second line of defence, but it runs after a push, so a secret it finds is already on GitHub.

## How we work

The team and agent rules are in [AGENTS.md](AGENTS.md). [CLAUDE.md](CLAUDE.md) is an identical copy, because Claude Code reads that file name.

In short:
- Every folder has one owner.
- Nobody pushes directly to `main`.
- Branches are named `<member letter>-<topic>`.
- PRs stay small, and merged branches are deleted.

## AI usage disclosure

We use AI coding assistants: Codex for Iliass Barrou, Ayman El Kerboubi and Taha Errassif, and Claude Code for Monssif El Haouari. Every agent session is logged in [docs/AI_USAGE.md](docs/AI_USAGE.md) with the tool, task, files and human reviewer.

## Team

| Member | Name | Role |
|---|---|---|
| A | Iliass Barrou | Tech lead, analytics engine |
| B | Ayman El Kerboubi | Data, health science and evaluation; main presenter |
| C | Taha Errassif | Frontend and UX; demo driver |
| D | Monssif El Haouari | Backend, security, data integrity and release |

## Acknowledgements and licences

- NASA Space Apps Challenge 2026 and its challenge resources.
- NASA Open Science Data Repository, study [OSD-575](https://osdr.nasa.gov/bio/repo/data/studies/OSD-575) (files in `download/`).
- NASA Curiosity RAD Level 2 data ([MSL_RAD_OBS-L2](https://data.nasa.gov/dataset/mars-science-laboratory-msl-radiation-assessment-detector-rad-level-2-observation-dosimetr)), exported by Ayman El Kerboubi (`raw data/NASA Curiosity radiation/`).
- The synthetic dataset's historical reference tables are cited in [iss-synthetic-3000/README.md](iss-synthetic-3000/README.md).
- 3D model: "Astronaut" by Javi_DaviYT on Sketchfab, CC BY 4.0 ([notice](frontend/public/licenses/Astronaut-model-NOTICE.txt)).
- Font: Inter, SIL Open Font License 1.1 ([licence](frontend/public/licenses/Inter-OFL.txt)).

**Licence:**
- The team's own code, documentation and synthetic data are under the [Apache License 2.0](LICENSE).
- The [2026 Space Apps Participant Terms](https://www.spaceappschallenge.org/legal/) require original content to be under an OSI open-source licence, and Apache 2.0 is what NASA uses when a team names none.
- Every third-party source and its licence is listed in [NOTICE](NOTICE). The terms require this documentation and citations.
