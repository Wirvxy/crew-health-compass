# Mode 1 offline Isolation Forest experiment

M3 runs alongside M2 in an explicit opt-in call for complete synthetic protocol rows. `assess_with_ml` returns the existing M2 result under `assessment` and the separate experiment under `ml_finding`. Person D can continue calling M2's `assess_check_in` directly for the default manual check-in flow. Use `assess_check_in_with_ml(payload, history, config=...)` when a client needs an explicit availability result. It returns the M2 assessment with a separate finding whose `model_available` is false and whose score and flag are null. The manual contract lacks equivalent full feature vectors and independently verified acquisition protocols.

## Features and fitting

| Protocol and context | Numeric features |
|---|---|
| Apollo–Soyuz `inflight_vitals_check` | Mean heart rate and peak heart rate in bpm, respiratory rate in breaths/min |
| Skylab `rest`, `exercise`, and `recovery` | Mean heart rate in bpm, systolic and diastolic blood pressure in mmHg, minute ventilation in L/min BTPS, oxygen uptake and CO₂ output in L/min STPD |
| Apollo 10 `morning_check` | Single heart-rate feature, excluded from the multivariable experiment |

One model per astronaut, protocol, and context requires at least 50 complete training normals. The pipeline checks source fields and units and skips incomplete vectors. Its matrix contains only the listed measurements. Crew ID, protocol, and activity are partition keys. Source context, row number, timestamps, and evaluation labels are excluded from the matrix. A StandardScaler is fitted inside each training pipeline. Isolation Forest uses 100 trees, seed 42, one worker, automatic subsample size, and 2% contamination as an experimental training cutoff. Positive `anomaly_score` means the negated scikit-learn decision score exceeded zero. The score is a model margin on its own fitted series.

Training used mission days 1–120, or 100 observed days, and evaluation used days 121–180, or 50 observed days. The cutoff is 2030-05-01 UTC. Of 2,000 early rows, 1,937 were synthetic normals. The 16 models used 1,559 of those normals, with 93–100 per model. The split rejects overlapping source keys and duplicate crew/protocol/context timestamps. Fitting rejects any row at or after the cutoff. Labels select training normals and score the holdout. Apollo–Soyuz uses the neutral M1 context so the source field that mirrors planted severity cannot be used for partitioning.

## Held-out results

All three approaches use the same 800 scored rows, comprising 780 normals, 19 mild scenarios, and one critical-priority drill. ML coverage is 800/1,000, or 80%. The remaining 200 are Apollo 10 rows, including 12 mild scenarios. M2 retains its usual rolling history through strictly earlier unlabeled observations, including earlier holdout rows. ML and its scaler stay frozen. Hybrid means either detector flagged the row, solely for evaluation. An M2 abstention with a negative ML result stays an abstention. All three approaches had zero abstentions on the shared set.

| Approach | Mild detected / missed | Critical detected / missed | False alarms / 780 normals | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| M2 | 16 / 3 | 1 / 0 | 70 | 19.5% | 85% | 0.318 |
| Isolation Forest | 18 / 1 | 1 / 0 | 24 | 44.2% | 95% | 0.603 |
| Hybrid | 19 / 0 | 1 / 0 | 92 | 17.9% | 100% | 0.303 |

Each cell below gives detected planted scenarios / false alarms. The CLI report includes raw severity counts, misses, precision, recall, F1, and scenario-level breakdowns.

| Scope | Scored | Planted | M2 | ML | Hybrid |
|---|---:|---:|---:|---:|---:|
| Commander | 200 | 5 | 2 / 17 | 5 / 6 | 5 / 22 |
| Flight Engineer 1 | 200 | 7 | 7 / 13 | 7 / 1 | 7 / 14 |
| Flight Engineer 2 | 200 | 4 | 4 / 25 | 3 / 11 | 4 / 36 |
| Flight Engineer 3 | 200 | 4 | 4 / 15 | 4 / 6 | 4 / 20 |
| Apollo–Soyuz vitals | 200 | 12 | 9 / 5 | 11 / 10 | 12 / 14 |
| Skylab rest | 200 | 0 | 0 / 28 | 0 / 10 | 0 / 37 |
| Skylab exercise | 200 | 0 | 0 / 22 | 0 / 2 | 0 / 24 |
| Skylab recovery | 200 | 8 | 8 / 15 | 8 / 2 | 8 / 17 |
| Skylab total | 600 | 8 | 8 / 65 | 8 / 14 | 8 / 78 |

ML improved aggregate precision and recall on the 800 shared rows. It missed one of the 12 high-workload scenarios. Every method detected the seven delayed-recovery examples and the single held-out escalation drill. Isolation Forest learns the simulator's distributions, and planted scenarios directly change the measurements used as features. The small, imbalanced holdout and absent manual-input validation limit generalization. Keep ML disabled in the final monitoring demo.

### Full holdout with coverage included

The full holdout contains 968 normals, 31 mild scenarios, and one critical-priority drill. On ML-ineligible rows, the hybrid evaluation falls back to M2. Misses include planted cases without an alarm, including abstentions. The report includes these counts under `full_holdout_metrics`.

| Approach | Mild detected / missed | Critical detected / missed | False alarms / 968 normals | Abstentions | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| M2 | 28 / 3 | 1 / 0 | 73 | 18 | 28.4% | 90.6% | 0.433 |
| Isolation Forest | 18 / 13 | 1 / 0 | 24 | 200 | 44.2% | 59.4% | 0.507 |
| Hybrid | 31 / 0 | 1 / 0 | 95 | 18 | 25.2% | 100% | 0.403 |

## Reproduce and load offline

Use the optional `scikit-learn==1.8.0` for training and inference and `skops==0.16.0` for persistence. This experiment was verified on Python 3.13. Install the packages into a local Python environment before going offline. Base engine tests and M2 use the standard library.

```powershell
New-Item -ItemType Directory -Force engine/build/mode1-ml
python -m engine.mode1_ml_evaluation --source path/to/iss-synthetic-3000.zip --model-out engine/build/mode1-ml/personal-forests.skops > engine/build/mode1-ml/evaluation.json
```

The tested ZIP SHA-256 is `358f3d51eb6a4deb457fdcb98b03ff44e16d4b52fbf0aa46888d31ea582dfb8d`. The JSON report and model metadata also identify the effective training data using a fingerprint of the ordered training-normal monitoring records. Output under `engine/build/` is ignored by Git. Use the same dependency versions when reloading.

The command reports `model_sha256`. Record it from your trusted local training run and pass it as `expected_sha256` to `load_models`. The loader checks the digest before deserialization and allows the specific scikit-learn tree type required by Isolation Forest. Use only artifacts you trained locally or received through a trusted, verified channel. A digest provided with an untrusted artifact does not establish trust.

```python
from engine.mode1_detection import HistoryIndex
from engine.mode1_ingestion import load_monitoring_data
from engine.mode1_ml import assess_with_ml, load_models

rows = load_monitoring_data("path/to/iss-synthetic-3000.zip")
history = HistoryIndex(rows)
models = load_models("engine/build/mode1-ml/personal-forests.skops", expected_sha256=recorded_digest)
result = assess_with_ml(rows[-1], history, models)
```

Omit the model argument to get the primary M2 assessment with an unavailable ML finding. Unsupported contexts or incomplete features also produce a null score and flag. The ML finding has the model and dataset version, crew, context, protocol, feature names, training count and end time, availability, score, flag, and limitations.
