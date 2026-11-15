# Backend API for the frontend: Mode 1 check-in and Mode 2 passport

For C (frontend), from D. The frontend uses these endpoints (PR #21). D keeps the response shapes stable; any change goes through a `contract-change` PR.

## 1. Start the backend locally

From the repository root, in PowerShell (the first two commands are needed only once):

```powershell
python -m venv api\.venv
api\.venv\Scripts\python.exe -m pip install -r api\requirements-dev.txt
api\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir api
```

- **Base URL:** `http://127.0.0.1:8000`. Interactive docs are at `http://127.0.0.1:8000/docs`.
- **Startup:** loads Person B's synthetic history (`data/mode1/`) and the NASA OSD-575 files (`data/mode2/`) once.
- **Offline:** everything comes from local files. Nothing is downloaded, and no external AI service is called.

## 2. Calling it from the frontend

Use relative paths such as `fetch('/api/monitoring/assess')`. In development, Vite's proxy (`frontend/vite.config.ts`) forwards `/api` and `/datasets` to port 8000, so the browser only talks to one origin and **no CORS is needed** (the team rules leave CORS out on purpose). Two settings exist: `DATASET_PROXY_TARGET` for the proxy target, and `VITE_API_BASE_URL` for a build that calls another origin. Both are described in `frontend/.env.example`.

## 3. Endpoints

| Method | Path | What it returns | Status |
|---|---|---|---|
| GET | `/health` | `{"status": "ok"}` while the server runs | existing |
| GET | `/api/monitoring/astronauts` | Synthetic crew IDs, contexts, and the time range of each history | **new** |
| POST | `/api/monitoring/assess` | Mode 1 statistical assessment of one manual check-in | **new** |
| GET | `/datasets/osd575/astronauts` | NASA crew IDs and visits | existing (A1) |
| GET | `/datasets/osd575/panels` | Panels, biomarkers and units | existing (A1) |
| GET | `/datasets/osd575/astronauts/{crew_id}/measurements?panel=&biomarker=` | Recorded values | existing (A1) |
| GET | `/datasets/osd575/astronauts/{crew_id}/postflight?panel=&biomarker=&visit=` | Postflight vs preflight average | existing (A2) |
| GET | `/datasets/osd575/astronauts/{crew_id}/trajectory?panel=&biomarker=` | One trajectory | existing (A3) |
| GET | `/datasets/osd575/comparison?panel=&biomarker=` | Four-astronaut comparison | existing (A3) |
| GET | `/datasets/osd575/astronauts/{crew_id}/passport?visit=R%2B45` | A4 biological passport | **new** |

The passport uses the crew-path form to match the four existing crew endpoints.

## 4. Mode 1: assess a manual check-in

### Request

`POST /api/monitoring/assess` with a JSON body:

| Field | Required | Format |
|---|---|---|
| `astronaut_id` | yes | `commander`, `flight_engineer_1`, `flight_engineer_2` or `flight_engineer_3` |
| `timestamp` | yes | ISO 8601 with a UTC offset, for example `2030-06-30T13:30:00Z` |
| `activity_context` | yes | `rest`, `exercise`, `recovery`, `morning_check`, `inflight_vitals_check` or `other` |
| `indicators.heart_rate` | yes | `{"value": "72", "unit": "bpm"}` |
| `indicators.respiratory_rate` | yes | `{"value": "15", "unit": "breaths/min"}` |
| `indicators.systolic_bp`, `indicators.diastolic_bp` | yes | `{"value": "112", "unit": "mmHg"}` |
| `indicators.sleep_duration` | no | `{"value": "7.5", "unit": "h"}` or null |
| `indicators.mood` | no | `low`, `fair`, `good` or `great` |
| `data_origin` | no | must be `user` if sent |

- **Values:** send them as strings to keep exact digits. JSON numbers are also accepted, and their digits are kept. Either way, write plain decimal numbers (see the checks below).
- **Units:** must match exactly.
- **Content type:** send the header `Content-Type: application/json`; any other type gets 415. Another website can make a visitor's browser send a `text/plain` or form POST without asking the server first. A JSON POST from another site needs the server's permission first (a CORS preflight), which this API never gives.
- **Checks:** A's validator rejects missing fields, unknown units, and negative or non-numeric values. The API then rejects, with 422, readings that cannot be real by definition (`api/app/checkin_checks.py`):
  - a value that is not a plain decimal number with up to 4 digits before the decimal point and 3 after: no sign, exponent (`1e3`) or spaces;
  - a heart rate, breathing rate or blood pressure of 0;
  - a systolic pressure that is not above the diastolic pressure;
  - more than 24 hours of sleep.
- **No medical limits:** these are format and logic checks only. Physiological ranges need a cited source and are still open, so a value such as 300 bpm is still assessed (as unusual).
- **Crew IDs:** these are fictional crew roles from the **synthetic** history. They are not the NASA crew C001–C004, so do not map one onto the other.

### What gets compared

A check-in is compared only with **strictly earlier** readings of the same astronaut, in the **same context** and with the same measurement protocol. At least 7 are needed, and the latest 14 are used.

| Context | Compared with history |
|---|---|
| `morning_check` | heart rate |
| `inflight_vitals_check` | heart rate, respiratory rate |
| `rest`, `exercise`, `recovery` | heart rate, systolic and diastolic BP, each within its own context |
| `other` | nothing (result: `insufficient_data`) |

Let the user choose the context; never pick `rest` or `exercise` for them. The history runs from **2030-01-01 to 2030-06-29 (UTC)**. For a demo, use a timestamp after that, such as `2030-06-30T13:30:00Z`. A real current date (2026) has no earlier history, so it returns `insufficient_data`. `GET /api/monitoring/astronauts` lists the exact ranges.

### Response

A's assessment, unchanged. Decimals are strings, and unavailable values are null.

| Field | Use it for |
|---|---|
| `overall_status` | `normal`, `unusual` or `insufficient_data` (`rule_supported_warning` is not produced yet) |
| `body_marker` | `chest`, `lungs`, `head` or null: where to show the indicator |
| `affected_systems` | `cardiovascular`, `respiratory`, `wellbeing` |
| `evidence[]` | Per indicator: value, unit, personal `baseline` (median), and `statistics` (including `history_origins: ["synthetic"]`) |
| `statistical_findings`, `explanation` | Text to show |
| `insufficient_data` | Reasons a value was not compared. **Show them even when the status is `normal`.** |
| `next_action_protocol_id` | Always null: there are no approved protocols, so show no advice |
| `optional_ml_findings` | Always null: the M3 Isolation Forest is off |

**Real examples** (request and response, produced by this API):
- [normal](examples/mode1/normal.json)
- [unusual](examples/mode1/unusual.json) (heart rate 85 vs median 66.5 bpm gives `chest`)
- [insufficient data](examples/mode1/insufficient-data.json)

**Label:** the history is SIMULATED. Show it as a statistical comparison with synthetic history, not as a diagnosis.

## 5. Mode 2: A4 biological passport

`GET /datasets/osd575/astronauts/C002/passport?visit=R%2B45` returns A's `build_biological_passport()` output unchanged. It is identical to A's [C002 R+45 example](../engine/biological_passport_examples/c002_r45.json), and a test checks this.

- **Crew:** `C001`–`C004`. **Visits:** `R+1`, `R+45`, `R+82`, `R+194`.
- **Encoding:** write `+` as `%2B`. `encodeURIComponent('R+45')` does this for you.
- **Display:** follow the "Person C" section of [A's guide](../engine/BIOLOGICAL_PASSPORT.md). In short:
  - `includes_later_observations: true` means the trajectory also uses visits after the selected one.
  - A lab interval `unavailable` is not a missing measurement.
  - Findings are not ranked by medical risk.

## 6. Errors

Errors from the new endpoints have one shape, `{"detail": "<message>"}`. [Real error examples](examples/mode1/errors.json).

| Status | When |
|---|---|
| 415 | The check-in was not sent as JSON (`Content-Type: application/json`). |
| 422 | Invalid check-in. The message starts with `Invalid check-in:` and then gives the reason from A's validator or the API's checks. |
| 404 | Unknown NASA crew, or a visit that is not postflight. The message lists the valid visits. |
| 503 | A dataset could not be loaded at startup. The message names no server path. |

Exception: when a required query parameter is missing on a GET endpoint (for example no `visit`), FastAPI returns 422 with a **list** in `detail`.

## 7. Open points

- **For A:** the contract accepts only `data_origin: "user"`, so a check-in filled with the frontend's example values is labelled as user data. How should simulated demo entries be marked?
- **For A:** value errors say "Expected a finite decimal value" without naming the field. Unit errors do name it.
- **For A or D:** the Mode 1 history chart needs the individual earlier readings, which the API does not return yet.
- **Storage:** check-ins are assessed but not stored, and they are not yet in the audit hash chain.
- **For B:** plausible physiological ranges (for example the highest heart rate a check-in may report) need a cited source in `catalogue/indicators.yaml`. Until then, only the format and logic checks above apply, and the "data problem" result is not defined.
