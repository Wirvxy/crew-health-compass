# NASA OSD-575 dataset API (for Person C)

Read-only endpoints that serve Person A's analysis of the NASA OSD-575 serum dataset: four Inspiration4 crew members, four panels, 302 biomarkers. The code is in `api/app/osd575.py`, and the data comes from A's `engine/`. The engine covers A1 ingestion, A2 postflight comparison and A3 trajectories.

> **Descriptive only.** These are laboratory comparisons, not clinical alerts, diagnoses or advice.
> - Show `lab_comparison`, `change_direction`, `baseline_status` and `trajectory_classification` as text. Do not turn them into green/amber/red health signals.
> - `closer`, `farther` and `mixed` describe the distance from the person's **own preflight average**. They are **not risk scores**.
> - Every response carries a `note` field, and trajectory responses also carry a `classification_note`.
>
> **Provisional.** The response envelopes and error messages are not in the shared contracts yet, and the project's error format is TBD at G1. The trajectory and comparison shapes (endpoints 5 and 6) wait for C's confirmation.
>
> **Separate from daily check-ins.** These endpoints live under `/datasets/osd575/`. They don't replace the planned check-in endpoints.

## Run it locally

From the repository root (A's `engine/` must be importable, so don't start it from `api/`):

```powershell
api\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir api
```

The server listens on `http://127.0.0.1:8000`. Data comes from the four `*_TRANSFORMED.csv` files in `data/mode2/`, or from the folder set in `CREW_HEALTH_OSD575_DIR`. Nothing is downloaded at runtime.

### Startup loading

When the server starts, it loads the CSVs once and runs A's A2 and A3 analyses (about 0.2 s). Requests then use those precomputed results, and nothing is re-read per request.

If the data is missing or unusable at startup:
- The server still starts, and `/health` still returns `{"status": "ok"}`, because it is only a liveness check.
- Every `/datasets/osd575/...` endpoint returns **503**, with a message that names the problem without any server path.
- The full error, including the path, is written to the server's error log.
- **Fixing the files requires a restart.** The server doesn't re-read them while it runs. This was tested live: copying the files into place while the server ran still gave 503, and a restart gave 200.

## Conventions

- **Numbers are strings.** Values, limits, baselines, changes and distances are exact decimal strings from A's serializers, for example `"77.33333333333333333333333333333333"`. Round them for display.
  - Some A3 results show a tiny remainder from the 34-digit arithmetic. For example, C001 glucose's `first_to_last_distance_change` is `"-3.000000000000000000000000000000003"`.
- **`null` means unavailable.** `value_status` says why (`missing` or `invalid`). In A2 results, `analysis_notes` explains it; in A3 results, `evidence_limitations` does.
- **Visit codes:**
  - `L-92`, `L-44` and `L-3` are days before launch.
  - `R+1`, `R+45`, `R+82` and `R+194` are days after return.
- **Encode `+` in URLs.** Use `visit=R%2B1`. JavaScript's `URLSearchParams` does this for you.
- **The panel is required** wherever a biomarker is named. The names `egf`, `lif` and `tslp` appear in both `eve_immune` and `alamar_immune`.
- **Every record keeps its units and provenance:** `unit`, `provenance: "dataset:OSD-575"`, and `source` (the exact CSV file, row and column).

## Endpoints

| # | Endpoint | Required parameters | Optional |
|---|---|---|---|
| 1 | `GET /datasets/osd575/astronauts` | none | none |
| 2 | `GET /datasets/osd575/panels` | none | none |
| 3 | `GET /datasets/osd575/astronauts/{crew_id}/measurements` | `panel` | `biomarker` |
| 4 | `GET /datasets/osd575/astronauts/{crew_id}/postflight` | `panel` | `biomarker`, `visit` |
| 5 | `GET /datasets/osd575/astronauts/{crew_id}/trajectory` (provisional) | `panel`, `biomarker` | none |
| 6 | `GET /datasets/osd575/comparison` (provisional) | `panel`, `biomarker` | none |
| 7 | `GET /datasets/osd575/astronauts/{crew_id}/passport` (A4) | `visit` (postflight, e.g. `R%2B45`) | none |

Endpoint 7 returns A's biological passport unchanged. It is described in [mode1-api.md, section 5](mode1-api.md#5-mode-2-a4-biological-passport) and [engine/BIOLOGICAL_PASSPORT.md](../engine/BIOLOGICAL_PASSPORT.md).

`crew_id` is `C001`–`C004`. `panel` is one of `cmp`, `eve_cardiovascular`, `eve_immune` or `alamar_immune`.

### 1. Astronauts

```json
{
  "study_id": "OSD-575", "provenance": "dataset:OSD-575",
  "note": "Descriptive comparison of NASA OSD-575 laboratory data. Not a clinical assessment, diagnosis or treatment advice.",
  "astronauts": [
    {"crew_id": "C001", "visits": ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]},
    "... C002, C003, C004"
  ]
}
```

The visit list covers all panels, and a single panel can be missing one visit (for example, `alamar_immune` has no C003 L-44 sample).

### 2. Panels

```json
{
  "study_id": "OSD-575", "provenance": "dataset:OSD-575", "note": "...",
  "panels": [
    {"panel": "cmp", "group": "metabolic",
     "biomarkers": [{"biomarker": "albumin", "unit": "g/dL"}, "... 19 in total"]},
    {"panel": "eve_cardiovascular", "group": "cardiovascular", "biomarkers": ["... 9"]},
    {"panel": "eve_immune", "group": "immune", "biomarkers": ["... 71"]},
    {"panel": "alamar_immune", "group": "immune", "biomarkers": ["... 203"]}
  ]
}
```

### 3. Measurement history (A1)

`/datasets/osd575/astronauts/C001/measurements?panel=cmp&biomarker=glucose` returns 7 records (preflight and postflight, in time order). Here is the one for R+1:

```json
{
  "study_id": "OSD-575", "provenance": "dataset:OSD-575", "note": "...",
  "crew_id": "C001", "panel": "cmp", "biomarker": "glucose", "count": 7,
  "measurements": [
    {"crew_id": "C001", "visit": "R+1", "phase": "postflight", "phase_day": 1,
     "source_sample_id": "C001_serum_R+1", "group": "metabolic", "panel": "cmp",
     "biomarker": "glucose", "value": "90", "unit": "mg/dL",
     "lab_ref_min": "65", "lab_ref_max": "99", "normalized_percent": null,
     "raw_value": "90", "raw_lab_ref_min": "65", "raw_lab_ref_max": "99",
     "raw_normalized_percent": null,
     "source": {"file": "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
                "row": 5, "value_column": "glucose_value_milligram_per_deciliter"},
     "provenance": "dataset:OSD-575", "value_status": "valid"}
  ]
}
```

### 4. Postflight comparison with the personal baseline (A2)

`/datasets/osd575/astronauts/C001/postflight?panel=cmp&biomarker=glucose&visit=R%2B1`

```json
{
  "study_id": "OSD-575", "provenance": "dataset:OSD-575", "note": "...",
  "crew_id": "C001", "panel": "cmp", "biomarker": "glucose", "visit": "R+1", "count": 1,
  "results": [
    {"crew_id": "C001", "panel": "cmp", "group": "metabolic", "biomarker": "glucose",
     "visit": "R+1", "phase": "postflight", "phase_day": 1, "source_sample_id": "C001_serum_R+1",
     "current_value": "90", "current_value_status": "valid", "raw_current_value": "90",
     "unit": "mg/dL", "baseline_value": "77.33333333333333333333333333333333",
     "baseline_status": "complete", "baseline_sample_count": 3,
     "valid_preflight_sample_ids": ["C001_serum_L-92", "C001_serum_L-44", "C001_serum_L-3"],
     "missing_preflight_sample_ids": [], "invalid_preflight_sample_ids": [],
     "absolute_change": "12.66666666666666666666666666666667",
     "percentage_change": "16.37931034482758620689655172413793",
     "change_direction": "increase", "lab_ref_min": "65", "lab_ref_max": "99",
     "raw_lab_ref_min": "65", "raw_lab_ref_max": "99",
     "lab_comparison": "within", "interval_coverage": "two_sided",
     "source": {"file": "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv", "row": 5,
                "value_column": "glucose_value_milligram_per_deciliter"},
     "study_id": "OSD-575", "provenance": "dataset:OSD-575", "analysis_notes": []}
  ]
}
```

### 5. One astronaut's trajectory (A3, provisional)

`/datasets/osd575/astronauts/C001/trajectory?panel=cmp&biomarker=glucose`. The `trajectory` object is A's `serialize_trajectory()` output, unchanged. Here it's trimmed to two of the four visits:

```json
{
  "study_id": "OSD-575", "provenance": "dataset:OSD-575", "note": "...",
  "classification_note": "trajectory_classification describes how the distance from this person's own preflight average changed across postflight visits. It is not a risk score.",
  "crew_id": "C001", "panel": "cmp", "biomarker": "glucose",
  "trajectory": {
    "crew_id": "C001", "panel": "cmp", "group": "metabolic", "biomarker": "glucose", "unit": "mg/dL",
    "baseline_value": "77.33333333333333333333333333333333", "baseline_status": "complete",
    "baseline_sample_count": 3,
    "valid_preflight_sample_ids": ["C001_serum_L-92", "C001_serum_L-44", "C001_serum_L-3"],
    "visits": [
      {"visit": "R+1", "phase_day": 1, "value": "90", "value_status": "valid",
       "change_from_baseline": "12.66666666666666666666666666666667",
       "distance_from_baseline": "12.66666666666666666666666666666667",
       "position_relative_to_baseline": "above", "change_direction": "unavailable",
       "distance_movement": null, "previous_valid_phase_day": null, "days_since_previous_valid": null,
       "lab_comparison": "within", "interval_coverage": "two_sided",
       "lab_ref_min": "65", "lab_ref_max": "99", "source_sample_id": "C001_serum_R+1",
       "source": {"file": "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv", "row": 5,
                  "value_column": "glucose_value_milligram_per_deciliter"}},
      {"visit": "R+45", "phase_day": 45, "value": "84", "value_status": "valid",
       "change_from_baseline": "6.666666666666666666666666666666667",
       "distance_from_baseline": "6.666666666666666666666666666666667",
       "position_relative_to_baseline": "above", "change_direction": "decrease",
       "distance_movement": "closer", "previous_valid_phase_day": 1, "days_since_previous_valid": 44,
       "lab_comparison": "within", "...": "..."},
      "... R+82 (91, farther), R+194 (87, closer)"
    ],
    "first_observation": {"visit": "R+1", "value": "90", "...": "same fields as a visit"},
    "last_observation": {"visit": "R+194", "value": "87", "...": "same fields as a visit"},
    "trajectory_classification": "mixed",
    "first_to_last_distance_change": "-3.000000000000000000000000000000003",
    "crossed_baseline": false, "measurement_direction_reversed": true,
    "valid_observation_count": 4, "missing_observation_count": 0, "invalid_observation_count": 0,
    "absent_visit_days": [], "evidence_limitations": [],
    "finding": "Movement toward or away from the preflight baseline changed direction.",
    "study_id": "OSD-575", "provenance": "dataset:OSD-575"
  }
}
```

Example with missing data: C002, `cmp`, `bun_to_creatinine_ratio`. All four postflight values are missing (fields trimmed):

```json
{
  "unit": "(calc)", "baseline_status": "insufficient_baseline",
  "trajectory_classification": "insufficient_data",
  "valid_observation_count": 0, "missing_observation_count": 4,
  "visits": [{"visit": "R+82", "value": null, "value_status": "missing",
              "change_from_baseline": null, "distance_from_baseline": null,
              "distance_movement": null, "lab_comparison": "unavailable", "...": "..."}],
  "evidence_limitations": ["A complete personal preflight baseline is unavailable.",
                           "Fewer than two valid postflight observations.",
                           "The postflight record contains unavailable observations."],
  "finding": "Insufficient observations or baseline for longitudinal comparison."
}
```

### 6. All four astronauts for one biomarker (A3, provisional)

`/datasets/osd575/comparison?panel=cmp&biomarker=glucose` is built with A's `compare_astronauts()`. Each entry in `trajectories` has the same shape as `trajectory` in endpoint 5, in crew ID order.

```json
{
  "study_id": "OSD-575", "provenance": "dataset:OSD-575", "note": "...", "classification_note": "...",
  "panel": "cmp", "biomarker": "glucose", "unit": "mg/dL", "count": 4,
  "trajectories": [
    {"crew_id": "C001", "baseline_value": "77.33333333333333333333333333333333",
     "trajectory_classification": "mixed", "crossed_baseline": false, "...": "..."},
    {"crew_id": "C002", "baseline_value": "73", "trajectory_classification": "mixed",
     "crossed_baseline": true, "...": "..."},
    {"crew_id": "C003", "baseline_value": "71.33333333333333333333333333333333", "...": "..."},
    {"crew_id": "C004", "baseline_value": "79.66666666666666666666666666666667", "...": "..."}
  ]
}
```

Each crew member keeps their **own** baseline. The first postflight glucose values are 90, 83, 103 and 97 mg/dL.

Values from A's engine:
- `trajectory_classification`: `consistently_closer`, `consistently_farther`, `mixed`, `unchanged_distance` or `insufficient_data`
- `distance_movement`: `closer`, `farther`, `unchanged` or `null`
- `position_relative_to_baseline`: `above`, `below`, `equal` or `null`
- `baseline_status`: `complete`, `insufficient_baseline` or `incompatible_units`
- `change_direction`: `increase`, `decrease`, `unchanged` or `unavailable`
- `lab_comparison`: `within`, `below`, `above` or `unavailable`

## Errors

These are real response bodies from the local server.

| Case | Status | Body |
|---|---|---|
| Unknown or malformed crew ID | 404 | `{"detail":"Unknown crew ID: 'C009'"}` |
| Unknown biomarker in that panel | 404 | `{"detail":"Unknown biomarker 'egf' in panel 'cmp'"}` |
| Missing `panel` or `biomarker` (endpoints 5 and 6) | 422 | `{"detail":[{"type":"missing","loc":["query","biomarker"],"msg":"Field required","input":null}]}` |
| Unknown panel | 422 | FastAPI validation error listing the four allowed panels |
| Visit with no postflight result (endpoint 4) | 404 | `{"detail":"No postflight result for visit 'L-3'. Postflight visits for C001: R+1, R+45, R+82, R+194."}` |
| Data missing at startup | 503 | `{"detail":"OSD-575 data file not found: LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv. Put the four OSD-575 TRANSFORMED CSV files in the folder set by CREW_HEALTH_OSD575_DIR (default: the repository's data/mode2/ folder), then restart the server. Nothing is downloaded at runtime."}` |
| Data unreadable at startup | 503 | `{"detail":"OSD-575 data files could not be read or analysed. Check that they are the original NASA TRANSFORMED CSV files, then restart the server."}` |

## Tested vs. assumed

**Tested locally** on 14 November 2026, on Windows with Python 3.14.3, on branch `d-osd575-api`:
- A's engine tests (`python -m unittest discover -s engine`): **34 of 34** passed.
- Backend tests (`python -m pytest` in `api/`): **69 of 69** passed, including 47 for these endpoints.
- C001 glucose at R+1: 90 mg/dL, baseline 77.33, change +12.67 (within ±0.005), `within`.
- C001 glucose trajectory:
  - values 90, 84, 91 and 87
  - movements none, closer, farther, closer
  - classification `mixed`
- Glucose comparison: C001–C004, with baselines 77.33, 73.00, 71.33 and 79.67.
- The A2 and A3 responses equal A's own serializer output exactly.
- All 302 panel and biomarker comparisons are strict JSON: no NaN, every number field is a finite decimal string or `null`, and only A's classification values appear.
- Errors: unknown and malformed crew IDs, unknown biomarkers and panels, and missing `panel` or `biomarker`.
- Startup:
  - The dataset loads exactly once, at startup, and not per request.
  - Without the startup step, the endpoints return 503 instead of loading.
  - Missing or unreadable data gives 503 without paths, and the error is logged.
  - Fixing the data needs a restart.
- Loading and analysis succeed with the network blocked.
- A live server produced the examples on this page and showed the startup-failure and restart behaviour.

**Assumed or not yet verified:**
- **Shapes:** the envelopes, error messages and the shapes of endpoints 5 and 6 wait for C's confirmation.
- **Linux and Python 3.11:** checked only by CI (see the integration PR). Locally only Python 3.14 was used.
- **Display:** rounding is left to the frontend.
