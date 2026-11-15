# Mode 1 ingestion and draft contracts

Person B's ISS simulation contains 3,000 **synthetic** observation rows. It uses historical NASA table formats as references. Crew, measurements, times, and evaluation scenarios are fictional.

## Load the data

Use Python 3.11 or later from the repository root. The default source is the repository's `data/mode1/` directory. On a branch without that directory, pass the path to Person B's ZIP or its extracted directory directly.

```python
from engine.mode1_ingestion import load_monitoring_data, select_series, serialize_observation

observations = load_monitoring_data("path/to/iss-synthetic-3000.zip")
series = select_series(
    observations,
    astronaut_id="commander",
    source_file="skylab4_inflight_exercise_iss_synthetic.csv",
    kind="heart_rate_mean_bpm",
    activity_context="recovery",
)
first_observation = serialize_observation(series[0][0])
```

Each observation carries `astronaut_id`, a UTC `timestamp`, `mission_day`, `activity_context`, optional safe `source_context`, `source_file`, one-based `source_row` excluding the header, `data_origin="synthetic"`, `provenance="simulated"`, and a tuple of readings. Each reading holds its original column name (`kind`), unit, `Decimal | None` value, raw CSV text, and `valid`, `missing`, or `invalid` status. JSON uses exact decimal strings, ISO timestamps, and null for unavailable readings. Joins validate a one-to-one row mapping, crew consistency, and UTC mission dates before sorting.

| Source format | Monitoring context | Readings |
|---|---|---|
| Apollo 10 | `morning_check` | Average heart rate (bpm) |
| Apollo–Soyuz | `inflight_vitals_check` | Mean and peak heart rate (bpm) and respiratory rate (breaths/min) |
| Skylab 4 | `rest`, `exercise`, `recovery` | Mean heart rate (bpm), systolic and diastolic BP (mmHg), ventilation (L/min BTPS), oxygen uptake and CO₂ output (L/min STPD) |

Crew IDs are the stable roles from `crew_profiles.json`. The display names Commander and Flight Engineer 1–3 map to `commander` and `flight_engineer_1` through `flight_engineer_3`. Keep source format, measurement kind, and context in the series key. Source row and filename provide provenance and an evaluation join key. Source row numbers and calendar order can encode how the simulation was generated, so exclude raw row indices from future model features.

## Evaluation labels

`load_evaluation_labels(source)` returns a separate list keyed by `(source_file, source_row)`. It supplies the expected severity, scenario, and original context for evaluation. Monitoring output omits expected severity and scenarios. Apollo–Soyuz's original `routine_check` and `high_workload_check` context maps exactly to the planted labels in this release, so use the neutral `inflight_vitals_check` context for its monitoring rows. Skylab preserves the CSV activity, including recovery, independently of the evaluation labels for delayed recovery and drills.

## Manual check-in and future assessment

- [Mock manual request](mode1_examples/manual_check_in.json) illustrates a user-entered check-in. `validate_manual_check_in(payload)` requires a nonempty ID, ISO 8601 timestamp with offset, activity context, HR, respiratory rate, and both BP values. Each numeric indicator carries its explicitly required unit. The validator accepts finite nonnegative decimal values without medical thresholds. Sleep in hours and mood may be omitted or null. The self-reported mood scale is the ordered categories `low`, `fair`, `good`, and `great`. The synthetic historical files have no sleep or mood series.
- [Mock assessment response](mode1_examples/mock_assessment.json) shows the draft display fields. `validate_assessment(payload)` checks shape and units and returns a JSON-compatible dictionary. Findings are arrays of strings. Optional ML findings can be null. Available evidence can include a baseline in the same unit. Status can be `normal`, `unusual`, `insufficient_data`, or `rule_supported_warning`. The warning shape requires rule and protocol IDs. Future assessment code must resolve those IDs against approved rules before producing warnings. M1 defines no rules or protocols.

Manual contexts are `rest`, `exercise`, `recovery`, `morning_check`, `inflight_vitals_check`, and `other`. Both validators return decimal strings so clients can retain precision. Send numeric inputs as strings to preserve precision through JSON parsing.

## Verify

With the dataset in the default repository directory, run `python -m unittest discover -s engine -v`. To use a local archive on PowerShell, set `$env:CREW_HEALTH_MODE1_DATA = 'C:\path\to\iss-synthetic-3000.zip'` first. Tests using the full dataset skip if the default path is absent and no override is set. An invalid explicit override fails the test setup.
