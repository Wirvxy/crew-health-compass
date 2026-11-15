# Crew Health Compass engine

Person A's analytics. Everything uses the Python standard library and runs offline, except the optional M3 experiment, which needs scikit-learn. Each part has its own guide:

| Part | Modules | Guide |
|---|---|---|
| Mode 2, A1–A3: OSD-575 ingestion, postflight comparison, trajectories | `nasa_ingestion.py`, `biomarker_analysis.py`, `trajectory_analysis.py` | this file (below) |
| Mode 2, A4: biological passport | `biological_passport.py` | [BIOLOGICAL_PASSPORT.md](BIOLOGICAL_PASSPORT.md) |
| Mode 1: synthetic data ingestion and contracts | `mode1_ingestion.py`, `mode1_contracts.py` | [MODE1_CONTRACT.md](MODE1_CONTRACT.md) |
| Mode 1: M2 personal statistical detection (used by the API) | `mode1_detection.py` | [MODE1_DETECTION.md](MODE1_DETECTION.md) |
| Mode 1: M3 Isolation Forest experiment (off in the API) | `mode1_ml.py`, `mode1_ml_evaluation.py` | [MODE1_ML.md](MODE1_ML.md) |
| Mission Environment, R1: Curiosity RAD radiation history | `radiation_history.py` | [RADIATION_HISTORY.md](RADIATION_HISTORY.md) |

JSON examples are in `biological_passport_examples/` and `mode1_examples/`. Tests are the `test_*.py` files: run `python -m unittest discover -s engine` from the repository root.

## NASA OSD-575 ingestion (A1)

The Phase A1 loader reads four transformed serum CSVs from [NASA OSD-575](https://osdr.nasa.gov/bio/repo/data/studies/OSD-575). It uses the Python standard library and runs offline.

## Data setup

Place these files directly in the repository's `data/mode2/` directory using their original names. If the checkout already contains them, use those copies.

- `LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv`
- `LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv`
- `LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv`
- `LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv`

If using the NASA ZIP, extract it first and point the loader at the directory containing the CSVs. The submitted CSVs and workbook are optional source references.

## Load and serialize records

From the repository root, run a quick check with:

```sh
python -c "from engine.nasa_ingestion import load_osd575; print(len(load_osd575()))"
```

In Python, `load_osd575()` defaults to the repository's `data/mode2/` regardless of your working directory. Pass a string or `Path` as `data_dir` to read from another directory. To load just one panel, call `load_osd575_panel(data_dir, panel)` with `cmp`, `eve_cardiovascular`, `eve_immune`, or `alamar_immune`.

```python
import json
from pathlib import Path

from engine.nasa_ingestion import load_osd575, serialize_measurement

records = load_osd575(data_dir=Path("path/to/extracted/csvs"))
payload = [serialize_measurement(record) for record in records]
json_text = json.dumps(payload, allow_nan=False)
```

In Python, numeric measurements, reference limits, and normalized percentages use `Decimal`. For JSON, `serialize_measurement()` emits finite decimals as **strings** to preserve precision, for example `"90.00"`. The strings can include exponent notation and can be read back with `Decimal`. Unavailable numeric fields become JSON `null`. The visit day and CSV line number remain JSON integers. The output includes the crew and sample IDs, biomarker, unit, phase, visit, and dataset and CSV provenance.

## Input errors and tests

- A required CSV that is absent raises `FileNotFoundError` with its expected path.
- Unexpected headers, wrong field counts, invalid sample IDs, duplicate samples within a panel, and files with no samples raise `ValueError`. These messages include the file path and, for row errors, the line number. CSV syntax and encoding errors can raise `csv.Error` and `UnicodeDecodeError`, respectively.
- An unreadable measurement cell still produces a record. Check `value_status` for `valid` (a finite value, including zero), `missing` (blank, `NA`, or `N/A`, allowing surrounding whitespace and any case), or `invalid` (other nonnumeric text, NaN, or infinity). Missing and invalid measurements both have `value=None` in Python and retain the original cell in `raw_value`.

With all four files in the default directory, run the suite from the repository root:

```sh
python -m unittest discover -s engine -v
```

The synthetic CSV tests use the system temporary directory. Set `TEMP` and `TMP` to a writable directory if your local environment restricts the default location.

## Postflight trajectories

Pass the A2 results to A3. For a comparison chart, select one panel and biomarker. The returned series keep each crew member's baseline, chronological visits, and source CSV coordinates.

```python
import json

from engine.biomarker_analysis import analyze_postflight
from engine.nasa_ingestion import load_osd575
from engine.trajectory_analysis import analyze_trajectories, compare_astronauts, serialize_trajectory

trajectories = analyze_trajectories(analyze_postflight(load_osd575()))
glucose = compare_astronauts(trajectories, panel="cmp", biomarker="glucose")
print(json.dumps([serialize_trajectory(series) for series in glucose], allow_nan=False))
```

Change and distance use the personal baseline from A2. A negative `first_to_last_distance_change` means the last valid visit was closer than the first. `mixed` covers reversals in distance movement and sequences with both movement and ties. `crossed_baseline` requires valid readings on both sides. `measurement_direction_reversed` tracks increases and decreases in the observed values and is null until at least two comparable steps exist.

Missing and invalid cells stay in `visits` with separate counts. An expected visit with no row appears in `absent_visit_days`. Consecutive valid readings use their actual day offsets, including across gaps. Two valid readings carry a limited-evidence note. The default expected postflight days are 1, 45, 82, and 194.

JSON uses exact decimal strings and null for unavailable fields. Interpret each series on its original assay scale. The measurements describe changes across discrete serum visits.
