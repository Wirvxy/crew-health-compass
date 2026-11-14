# NASA Health Replay data ingestion

The Phase A1 loader reads four transformed serum CSVs from [NASA OSD-575](https://osdr.nasa.gov/bio/repo/data/studies/OSD-575). It uses the Python standard library and runs offline.

## Data setup

Place these files directly in the repository's `download/` directory using their original names. If the checkout already contains them, use those copies.

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

In Python, `load_osd575()` defaults to the repository's `download/` regardless of your working directory. Pass a string or `Path` as `data_dir` to read from another directory. To load just one panel, call `load_osd575_panel(data_dir, panel)` with `cmp`, `eve_cardiovascular`, `eve_immune`, or `alamar_immune`.

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
