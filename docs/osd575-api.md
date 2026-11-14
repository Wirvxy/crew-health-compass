# NASA OSD-575 dataset API (for Person C)

Read-only endpoints that serve Person A's analysis of the NASA OSD-575 serum dataset: four Inspiration4 crew members, four panels, 302 biomarkers. The code is in `api/app/osd575.py`, and the data comes from A's `engine/`.

> **Descriptive only.** These are laboratory comparisons, not clinical alerts, diagnoses or advice. Show `lab_comparison`, `change_direction` and `baseline_status` as text. Do not turn them into green/amber/red health signals. Every response carries a `note` field saying this.
>
> **Provisional.** The response envelopes and error messages are not in the shared contracts yet. The project's error format is TBD at G1, and A and C should confirm these shapes.
>
> **Separate from daily check-ins.** These endpoints live under `/datasets/osd575/`. They don't replace the planned check-in endpoints (`/astronauts/{id}/status`, `/astronauts/{id}/history`).

## Run it locally

From the repository root (A's `engine/` must be importable, so don't start it from `api/`):

```powershell
api\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir api
```

The server listens on `http://127.0.0.1:8000`. Data comes from the four `*_TRANSFORMED.csv` files in `download/`, or from the folder set in `CREW_HEALTH_OSD575_DIR`. Nothing is downloaded at runtime.

## Conventions

- **Numbers are strings.** Values, limits, baselines and changes are exact decimal strings from A's serializers, for example `"77.33333333333333333333333333333333"`. Round them for display (for example, to 2 decimals). Don't round before comparing.
- **`null` means unavailable.** For a measurement, `value_status` says why (`missing` or `invalid`), and `raw_value` holds the original cell text. For an analysis result, `analysis_notes` explains it.
- **Visit codes:**
  - `L-92`, `L-44` and `L-3` are days before launch (preflight).
  - `R+1`, `R+45`, `R+82` and `R+194` are days after return (postflight).
  - `phase_day` gives the same number as an integer: negative before launch, positive after return.
- **Encode `+` in URLs.** Use `visit=R%2B1`, not `visit=R+1` (in a query string, `+` means a space). JavaScript's `URLSearchParams` does this for you.
- **The panel is always required.** The names `egf`, `lif` and `tslp` appear in both `eve_immune` and `alamar_immune`.
- **Every record keeps its units and provenance.** That includes `unit`, `provenance: "dataset:OSD-575"`, and `source` (the exact CSV file, row and column).

## Endpoints

### 1. `GET /datasets/osd575/astronauts`

This returns the crew IDs, each with its visit codes in time order. The visit list covers all panels, and a single panel can be missing one visit (for example, `alamar_immune` has no C003 L-44 sample).

```json
{
  "study_id": "OSD-575",
  "provenance": "dataset:OSD-575",
  "note": "Descriptive comparison of NASA OSD-575 laboratory data. Not a clinical assessment, diagnosis or treatment advice.",
  "astronauts": [
    {"crew_id": "C001", "visits": ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]},
    "... C002, C003, C004"
  ]
}
```

### 2. `GET /datasets/osd575/panels`

This returns the four panels, each with its biomarkers and units (302 biomarkers in total).

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

### 3. `GET /datasets/osd575/astronauts/{crew_id}/measurements`

This returns all visits (preflight and postflight) for one crew member, in time order.

| Parameter | Required | Values |
|---|---|---|
| `crew_id` (path) | yes | `C001`–`C004` |
| `panel` | yes | `cmp`, `eve_cardiovascular`, `eve_immune`, `alamar_immune` |
| `biomarker` | no | a name from `/panels`. Leave it out for every biomarker in the panel; `alamar_immune` then returns about 1,400 records |

Example: `/datasets/osd575/astronauts/C001/measurements?panel=cmp&biomarker=glucose` returns 7 records. Here is the one for R+1:

```json
{
  "study_id": "OSD-575", "provenance": "dataset:OSD-575", "note": "...",
  "crew_id": "C001", "panel": "cmp", "biomarker": "glucose", "count": 7,
  "measurements": [
    {
      "crew_id": "C001", "visit": "R+1", "phase": "postflight", "phase_day": 1,
      "source_sample_id": "C001_serum_R+1", "group": "metabolic", "panel": "cmp",
      "biomarker": "glucose", "value": "90", "unit": "mg/dL",
      "lab_ref_min": "65", "lab_ref_max": "99", "normalized_percent": null,
      "raw_value": "90", "raw_lab_ref_min": "65", "raw_lab_ref_max": "99",
      "raw_normalized_percent": null,
      "source": {"file": "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
                 "row": 5, "value_column": "glucose_value_milligram_per_deciliter"},
      "provenance": "dataset:OSD-575", "value_status": "valid"
    }
  ]
}
```

### 4. `GET /datasets/osd575/astronauts/{crew_id}/postflight`

This returns A's comparison of each postflight value with the crew member's own preflight baseline. The baseline is the mean of at least 3 valid preflight readings. The response also says whether the value is within, below or above the lab's reference range, where one exists (only `cmp` has ranges).

| Parameter | Required | Values |
|---|---|---|
| `crew_id` (path) | yes | `C001`–`C004` |
| `panel` | yes | as above |
| `biomarker` | no | as above |
| `visit` | no | `R+1`, `R+45`, `R+82`, `R+194` (encode `+` as `%2B`) |

Example: `/datasets/osd575/astronauts/C001/postflight?panel=cmp&biomarker=glucose&visit=R%2B1`

```json
{
  "study_id": "OSD-575", "provenance": "dataset:OSD-575", "note": "...",
  "crew_id": "C001", "panel": "cmp", "biomarker": "glucose", "visit": "R+1", "count": 1,
  "results": [
    {
      "crew_id": "C001", "panel": "cmp", "group": "metabolic", "biomarker": "glucose",
      "visit": "R+1", "phase": "postflight", "phase_day": 1,
      "source_sample_id": "C001_serum_R+1",
      "current_value": "90", "current_value_status": "valid", "raw_current_value": "90",
      "unit": "mg/dL",
      "baseline_value": "77.33333333333333333333333333333333",
      "baseline_status": "complete", "baseline_sample_count": 3,
      "valid_preflight_sample_ids": ["C001_serum_L-92", "C001_serum_L-44", "C001_serum_L-3"],
      "missing_preflight_sample_ids": [], "invalid_preflight_sample_ids": [],
      "absolute_change": "12.66666666666666666666666666666667",
      "percentage_change": "16.37931034482758620689655172413793",
      "change_direction": "increase",
      "lab_ref_min": "65", "lab_ref_max": "99",
      "raw_lab_ref_min": "65", "raw_lab_ref_max": "99",
      "lab_comparison": "within", "interval_coverage": "two_sided",
      "source": {"file": "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
                 "row": 5, "value_column": "glucose_value_milligram_per_deciliter"},
      "study_id": "OSD-575", "provenance": "dataset:OSD-575", "analysis_notes": []
    }
  ]
}
```

Example with a missing value: C002, `cmp`, `bun_to_creatinine_ratio`, R+82 (selected fields):

```json
{
  "current_value": null, "current_value_status": "missing", "raw_current_value": "",
  "unit": "(calc)", "baseline_value": null, "baseline_status": "insufficient_baseline",
  "absolute_change": null, "percentage_change": null,
  "change_direction": "unavailable", "lab_comparison": "unavailable",
  "analysis_notes": ["Personal change requires 3 valid preflight readings.",
                     "Current measurement is missing."]
}
```

Status values (from A's engine):
- `baseline_status`: `complete`, `insufficient_baseline` or `incompatible_units`
- `change_direction`: `increase`, `decrease`, `unchanged` or `unavailable`
- `lab_comparison`: `within`, `below`, `above` or `unavailable`
- `interval_coverage`: `two_sided`, `lower_only`, `upper_only`, `none` or `invalid`

## Errors

These are the real response bodies from the local server.

| Case | Status | Body |
|---|---|---|
| Unknown or malformed crew ID | 404 | `{"detail":"Unknown crew ID: 'C009'"}` |
| Unknown biomarker in that panel | 404 | `{"detail":"Unknown biomarker 'egf' in panel 'cmp'"}` |
| Unknown panel | 422 | FastAPI validation error: `{"detail":[{"type":"literal_error","loc":["query","panel"],"msg":"Input should be 'cmp', 'eve_cardiovascular', 'eve_immune' or 'alamar_immune'", ...}]}` |
| Visit with no postflight result | 404 | `{"detail":"No postflight result for visit 'L-3'. Postflight visits for C001: R+1, R+45, R+82, R+194."}` |
| Unencoded `+` in `visit` | 404 | The same message, plus `In URLs, write '+' as %2B (R%2B1).` |
| Data file missing | 503 | `{"detail":"OSD-575 data file not found: LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv. Put the four OSD-575 TRANSFORMED CSV files in the folder set by CREW_HEALTH_OSD575_DIR (default: the repository's download/ folder). Nothing is downloaded at runtime."}` |

When the data is missing, `/health` still returns 200, and the next request tries to load the files again.

## Tested vs. assumed

**Tested** on 14 November 2026, on Windows with Python 3.14.3, on branch `d-osd575-api`:
- A's engine tests: 25 of 25 passed.
- Backend tests: 45 of 45 passed, including 23 for these endpoints.
- C001 glucose at R+1: value 90 mg/dL, baseline 77.33 and change +12.67 (within ±0.005), `within`.
  - This matches the raw CSV (83, 80 and 69 preflight) and A's own serializer output exactly.
- Missing values come back as `null`, with their status and raw text.
- Every response for all 4 crew members × 4 panels is strict JSON: no NaN, and every number field is a finite decimal string or `null`.
- Errors: unknown and malformed crew IDs, unknown biomarkers and panels, and a missing data file (503, without server paths).
- Loading and analysis succeed with the network blocked.
- The dataset is loaded once across many requests. The first load plus analysis took about 0.13 s.
- A live server on `127.0.0.1:8000` produced every example on this page.

**Assumed or not yet verified:**
- **Shapes:** the envelope (`study_id`, `provenance`, `note`, `count`, …) and the error messages are proposals, waiting for A and C to confirm.
- **CI:** not yet run on Linux. A's `unittest` suite isn't in CI yet.
- **Display:** rounding is left to the frontend.
- **Scope:** only A's approved commit `8475de9` is included, not the later trajectory analysis on `engine-main`.
