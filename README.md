# Crew Health Compass

An offline-first self-assessment prototype for astronauts on long missions, built in 48 hours for the **NASA Space Apps Challenge 2026**: *Create Health Monitoring Software for Astronauts on Space Missions*.

> **Hackathon prototype.** This is not a medical device. It is not clinically validated and does not comply with any health-data regulation. Demo data is **SIMULATED** and labelled that way, unless a named dataset is cited.
>
> **Status:** in progress. This README is a skeleton. It will be finished at gate G6 (H40).

## What it does

An astronaut logs a daily check, such as heart rate, blood pressure, body temperature, sleep hours and mood, plus blood glucose or SpO2 if available. The team confirms the final six indicators at G1.

An analytics engine compares each value with two references:

1. **Fixed clinical limits** from a cited indicator catalogue.
2. **The astronaut's own recent baseline**, plus the recent trend.

The result is a green, amber or red status for four body systems: cardiovascular, sleep/behavioural, metabolic and thermal. The statuses appear on a clickable body map. Each flag opens a guidance card that gives three things:

- why the value was flagged
- the source behind the rule
- what to do next: self-care, re-measure, call the crew medical officer, or send a report to the flight surgeon

A message from Mars to Earth takes 4–24 minutes one way. For that reason, the core health assessment runs offline and does not use external AI APIs. The report for the flight surgeon is a small packet that can be checked on arrival.

## How it works

This section describes the planned design. The status of each protection is in the [security table](#security-and-data-integrity).

1. The astronaut enters a value in the React UI (`frontend/`).
2. The FastAPI backend (`api/`) checks three things: the value is well-formed, it is physically plausible, and the sender is allowed to send it. The API is the **trust boundary**: no data reaches storage or the engine without passing these checks.
3. The value is stored in SQLite with a **hash-chained audit log**. Each record includes a fingerprint of the previous record, so editing a stored record can be detected.
4. The engine (`engine/`) applies the rules in `catalogue/indicators.yaml` and returns statuses, flags and reasons.
5. The UI shows the body map, trend charts and guidance cards.
6. *(If time permits)* the app builds a **signed report packet** for the flight surgeon, who can check that it was not changed in transit.

Everything ships as one Docker container, with FastAPI serving the built frontend. The same image runs on a laptop and on a free host for the public demo link.

## Repository layout

| Path | Contents | Owner |
|---|---|---|
| `contracts/` | Shared data models, JSON schemas, example fixtures | A |
| `engine/` | Analytics: fixed limits, personal baseline, trend | A |
| `catalogue/` | `indicators.yaml`: units, limits, guidance, cited sources | B |
| `data/` | Simulator and demo scenarios | B |
| `eval/` | Evaluation: fixed limits only vs. personal baseline | B |
| `frontend/` | React/Vite user interface | C |
| `api/` | FastAPI app, SQLite storage, validation, role checks | D |
| `security/` | Audit chain, report signing, threat model, security tests | D |
| `.github/workflows/`, `Dockerfile` | CI and deployment | D |
| `docs/` | AI-usage log and project notes | *Proposal:* D (everyone adds their own line to `docs/AI_USAGE.md`) |
| `download/` | NASA data files uploaded at kickoff (see [Data](#data-and-provenance)) | *Proposal:* B; nobody moves or deletes these files until B decides |

Each folder is created when its owner starts work. A confirms this layout at G1.

## Running locally

*Not available yet.* Setup and run commands will be added here when the API skeleton is ready (H2–H4). The local Docker run will be documented by H8.

## Data and provenance

Every measurement has a `provenance` field that records where it came from: `user`, `simulated`, or `dataset:<name>`. These values are confirmed at G1. The UI shows a visible **SIMULATED** label on simulated data.

### Files in `download/` (pending B's verification)

A teammate uploaded these files at kickoff. D read the copies in this repository, but **B has not yet checked them against the official source**. Each row below says only what the files themselves state, and where. The metadata files are in `download/OSD-575_metadata_OSD-575-ISA/`.

| What the files state | Evidence in the repository |
|---|---|
| NASA Open Science Data Repository study OSD-575: "SpaceX Inspiration4 Blood Serum Metabolic Panel and Immune/Cardiac Cytokine Arrays" | `i_Investigation.txt`: `Study Identifier`, `Study Title` |
| Inspiration4 mission, 16–18 September 2021, "four private astronauts"; public release 14 May 2024 | `i_Investigation.txt`: `Comment[Mission Name]`, `Comment[Mission Start]`, `Comment[Mission End]`, `Study Description`, `Study Public Release Date` |
| Four subjects with coded IDs C001–C004 | `SUBJECT_ID` column of `LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv`; `ID` column of both Eve Panel `_SUBMITTED.csv` files; `Source Name` in `s_OSD-575.txt` |
| Each subject's sex is recorded | `SEX` column (`F`, `M`) of the metabolic panel `_SUBMITTED.csv`; `Characteristics[Sex]` (`Female`, `Male`) in `s_OSD-575.txt` |
| Samples only from before launch and after return: L-92, L-44, L-3 ("Launch minus N" days) and R+1, R+45, R+82, R+194 ("Return plus N" days) | `timepoint` column of the metabolic panel `_SUBMITTED.csv`; `Factor Value[Time]` in `s_OSD-575.txt` |
| Blood tests, not daily check-in vitals: 19 metabolic panel analytes plus immune and cardiac cytokine panels. Of our candidate indicators, only glucose appears. | `ANALYTE` column of the metabolic panel `_SUBMITTED.csv`; `Type` column (`HD71`, `HDCVD9`) of the Eve Panel `_SUBMITTED.csv` files |
| The `.zip` holds the same six metadata files as the extracted folder | Each file in the zip is byte-identical to its committed copy (`git show HEAD:<path>`) |

**Not yet checked (for B):** the OSDR web page itself, the data licence and terms of use, whether these files exactly match the official download, and what the values mean clinically.

**Open question for the team:** the Inspiration4 crew is publicly known, so coded IDs plus recorded sex may not keep individuals anonymous. The team should decide before any of this data appears in the public demo.

## Security and data integrity

The security scope is kept small enough to finish in 48 hours. Each protection below will be tested only on our local prototype.

| Protection | What it does | Status |
|---|---|---|
| Input validation and plausibility checks | Malformed values and unknown units are refused with HTTP 422. Physically impossible values become a "data problem, re-measure" result instead of a medical alarm. | Planned (H2–H11) |
| Demo access control | Every request carries a fixed demo token for one of two roles: astronaut or flight surgeon. The server uses the token for basic **authentication** (identifying the caller through the token) and **authorization** (checking what that caller may access). An astronaut's token therefore reads only that astronaut's data. | Planned (H8–H14) |
| Hash-chained audit log | `GET /audit/verify` names the first stored record that no longer matches its fingerprint. | Built and tested locally. No measurements are stored in it yet, and the response shape is provisional |
| Secret and dependency scanning | CI runs npm audit, pip-audit, and a gitleaks scan of the full Git history on every pull request and every push to `main`. Binary files are not scanned for secrets. | Running in CI. The gitleaks job is new in this change |
| Encryption at rest | Measurement values are encrypted inside the SQLite file. | Planned (H6–H8) |
| Signed report packet | Ed25519 signature. Changing one byte makes verification fail. | Planned, if time permits (H24–H30) |

Each protection stays **Planned** until it is implemented and tested.

**Known limits:**

- Demo access control is **not** production-ready account management. There are no user accounts, no passwords, and the tokens are fixed demo values. Anyone who has a token can act as that caller. A token that is shared or publicly exposed, for example on the public demo, does not establish a private user identity.
- The hash chain detects edits to stored records. It has two blind spots. Someone who can write to the database file can change a record and recompute every later hash, because the hash uses no secret key. Deleting records from the end also leaves a valid, shorter chain. Future work: sign the latest hash or keep a copy somewhere else.
- The encryption key is an environment variable on the same machine, so encryption at rest only protects a database file that has been copied elsewhere. Future work: hardware-backed key storage.
- `.gitignore` lists files such as `.env` and `*.key` so that `git add` skips them by accident. It is not a guarantee:
  - it has no effect on a file that is already tracked
  - `git add -f` overrides it
  - it cannot see a secret pasted into an ordinary file

  Everyone checks their own diff before committing, and the gitleaks scan in CI is the second line of defence. It runs only after a push, so a secret it finds is already in the Git history on GitHub. Local secrets belong in `.env`; `.env.example` lists the variable names with placeholder values.

## How we work

The team and agent rules are in [AGENTS.md](AGENTS.md). [CLAUDE.md](CLAUDE.md) is an identical copy, because Claude Code reads that file name. In short: every folder has one owner, nobody pushes directly to `main`, PRs stay small, and merges happen in windows every two hours.

## AI usage disclosure

We use AI coding assistants: Codex for members A, B and C, and Claude Code for member D. Every agent session is logged in `docs/AI_USAGE.md` with the tool, task, files and human reviewer. The full disclosure required by the event will be added here at G6.

## Team

| Member | Role |
|---|---|
| A | Tech lead, analytics engine |
| B | Data, health science and evaluation; main presenter |
| C | Frontend and UX; demo driver |
| D | Backend, security, data integrity and release |

## Acknowledgements

- NASA Space Apps Challenge 2026 and its challenge resources.
- NASA Open Science Data Repository, study OSD-575 (files in `download/`; how the project uses them is pending B's review).
