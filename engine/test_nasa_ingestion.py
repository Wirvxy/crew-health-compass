import csv
import json
import tempfile
import unittest
from collections import Counter
from decimal import Decimal
from pathlib import Path

from engine.nasa_ingestion import (
    DEFAULT_DATA_DIR,
    load_osd575,
    load_osd575_panel,
    serialize_measurement,
)


class NASAIngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_osd575()
        cls.by_key = {
            (row.panel, row.source_sample_id, row.biomarker): row for row in cls.rows
        }

    def test_loads_all_panels_and_crew(self):
        coverage = {
            "cmp": (28, 19, 509),
            "eve_cardiovascular": (28, 9, 252),
            "eve_immune": (28, 71, 1988),
            "alamar_immune": (27, 203, 5481),
        }
        self.assertEqual({row.panel for row in self.rows}, set(coverage))
        for panel, (sample_count, biomarker_count, value_count) in coverage.items():
            with self.subTest(panel=panel):
                rows = [row for row in self.rows if row.panel == panel]
                usable_biomarkers = {row.biomarker for row in rows if row.value is not None}
                self.assertEqual({row.crew_id for row in rows}, {"C001", "C002", "C003", "C004"})
                self.assertEqual(len({row.source_sample_id for row in rows}), sample_count)
                self.assertEqual(len(usable_biomarkers), biomarker_count)
                self.assertEqual(sum(row.value is not None for row in rows), value_count)
                self.assertEqual(len(rows), sample_count * biomarker_count)
        alamar_samples = {row.source_sample_id for row in self.rows if row.panel == "alamar_immune"}
        self.assertNotIn("C003_serum_L-44", alamar_samples)

    def test_visit_classification_and_offsets(self):
        visits = {
            "L-92": ("preflight", -92),
            "L-44": ("preflight", -44),
            "L-3": ("preflight", -3),
            "R+1": ("postflight", 1),
            "R+45": ("postflight", 45),
            "R+82": ("postflight", 82),
            "R+194": ("postflight", 194),
        }
        for row in self.rows:
            self.assertEqual((row.phase, row.phase_day), visits[row.visit])
        self.assertEqual(
            Counter(row.phase for row in self.rows if row.panel == "cmp" and row.biomarker == "glucose"),
            {"preflight": 12, "postflight": 16},
        )

    def test_values_units_and_reference_limits(self):
        glucose = self.by_key["cmp", "C001_serum_R+1", "glucose"]
        self.assertEqual((glucose.value, glucose.unit), (Decimal("90"), "mg/dL"))
        self.assertEqual((glucose.lab_ref_min, glucose.lab_ref_max), (Decimal("65"), Decimal("99")))
        alt = self.by_key["cmp", "C001_serum_L-3", "alt"]
        self.assertEqual((alt.unit, alt.lab_ref_max), ("U/L", Decimal("46")))
        for panel, biomarker, expected in [
            ("eve_cardiovascular", "a2_macroglobulin", ("903742.69", "ng/ml", "61.94727616")),
            ("eve_immune", "6ckine", ("862.46", "pg/ml", "82.71668581")),
            ("alamar_immune", "activin_a", ("12.71515636", "NPQ", "99.13521005")),
        ]:
            with self.subTest(panel=panel):
                row = self.by_key[panel, "C001_serum_L-92", biomarker]
                value, unit, percent = expected
                self.assertEqual(
                    (row.value, row.unit, row.normalized_percent),
                    (Decimal(value), unit, Decimal(percent)),
                )
                self.assertIsNone(row.lab_ref_min)
                self.assertIsNone(row.lab_ref_max)

    def test_preserves_missing_values_and_one_sided_limits(self):
        blank = self.by_key["cmp", "C002_serum_R+82", "bun_to_creatinine_ratio"]
        missing = self.by_key["cmp", "C001_serum_L-44", "bun_to_creatinine_ratio"]
        egfr = self.by_key["cmp", "C001_serum_L-3", "egfr_african_american"]
        self.assertEqual((blank.value, blank.raw_value), (None, ""))
        self.assertEqual((missing.value, missing.raw_value), (None, "NA"))
        self.assertEqual(
            (egfr.lab_ref_min, egfr.lab_ref_max, egfr.raw_lab_ref_max),
            (Decimal("60"), None, "N/A"),
        )

    def test_provenance_points_to_actual_csv_cells(self):
        for row in (
            self.by_key["cmp", "C004_serum_R+1", "glucose"],
            self.by_key["alamar_immune", "C001_serum_L-92", "activin_a"],
        ):
            with self.subTest(panel=row.panel):
                self.assertEqual(row.provenance, "dataset:OSD-575")
                path = DEFAULT_DATA_DIR / row.source.file
                with path.open(encoding="utf-8-sig", newline="") as file:
                    reader = csv.DictReader(file)
                    record = next(record for record in reader if reader.line_num == row.source.row)
                self.assertEqual(next(iter(record.values())), row.source_sample_id)
                self.assertEqual(record[row.source.value_column], row.raw_value)

    def test_submitted_files_do_not_duplicate_measurements(self):
        self.assertEqual(len(self.rows), len(self.by_key))
        self.assertTrue(all(row.source.file.endswith("_TRANSFORMED.csv") for row in self.rows))

    def test_invalid_numeric_values_are_retained_as_raw_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / self.rows[0].source.file
            path.write_text(
                "Sample Name,example_value,example_range_min,example_range_max\n"
                "C001_serum_L-3,NaN,invalid,1\n"
                "C002_serum_R+1,0,0,1\n",
                encoding="utf-8",
            )
            invalid, zero = load_osd575_panel(directory, "cmp")
        self.assertEqual((invalid.value, invalid.raw_value), (None, "NaN"))
        self.assertEqual((invalid.lab_ref_min, invalid.raw_lab_ref_min), (None, "invalid"))
        self.assertEqual((zero.value, zero.lab_ref_min), (Decimal("0"), Decimal("0")))

    def test_classifies_primary_measurements_and_preserves_raw_text(self):
        cases = [
            ("0", "valid", Decimal("0")),
            (" -2.50 ", "valid", Decimal("-2.50")),
            ("", "missing", None),
            ("  ", "missing", None),
            ("NA", "missing", None),
            (" n/a ", "missing", None),
            ("below range", "invalid", None),
            ("NaN", "invalid", None),
            ("Infinity", "invalid", None),
            ("-inf", "invalid", None),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / self.rows[0].source.file
            with path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(
                    ["Sample Name", "example_value", "example_range_min", "example_range_max"]
                )
                for day, (raw, _, _) in enumerate(cases, start=1):
                    writer.writerow([f"C001_serum_L-{day}", raw, "", ""])
            records = load_osd575_panel(directory, "cmp")
        self.assertEqual(
            [(row.raw_value, row.value_status, row.value) for row in records], cases
        )
        serialized = [serialize_measurement(row) for row in records]
        payload = json.loads(json.dumps(serialized, allow_nan=False))
        self.assertEqual([row["value_status"] for row in payload], [status for _, status, _ in cases])
        self.assertEqual([row["value"] for row in payload], ["0", "-2.50"] + [None] * 8)
        self.assertEqual([row["raw_value"] for row in payload], [raw for raw, _, _ in cases])

    def test_serializes_exact_decimals_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / self.rows[0].source.file
            path.write_text(
                "Sample Name,glucose_value_milligram_per_deciliter,"
                "glucose_range_min_milligram_per_deciliter,glucose_range_max_milligram_per_deciliter\n"
                "C002_serum_R+1,85.123456789012345678901234567890,65.000,N/A\n",
                encoding="utf-8",
            )
            row, = load_osd575_panel(directory, "cmp")
        payload = json.loads(json.dumps(serialize_measurement(row), allow_nan=False))
        self.assertEqual(payload["value"], "85.123456789012345678901234567890")
        self.assertEqual(payload["lab_ref_min"], "65.000")
        self.assertIsNone(payload["lab_ref_max"])
        self.assertEqual(payload["unit"], "mg/dL")
        self.assertEqual(payload["crew_id"], "C002")
        self.assertEqual(payload["source_sample_id"], "C002_serum_R+1")
        self.assertEqual(payload["biomarker"], "glucose")
        self.assertEqual(
            (payload["visit"], payload["phase"], payload["phase_day"]), ("R+1", "postflight", 1)
        )
        self.assertEqual(payload["provenance"], "dataset:OSD-575")
        self.assertEqual(
            payload["source"],
            {"file": path.name, "row": 2, "value_column": "glucose_value_milligram_per_deciliter"},
        )
        alamar = self.by_key["alamar_immune", "C001_serum_L-92", "activin_a"]
        self.assertEqual(serialize_measurement(alamar)["normalized_percent"], "99.13521005")

    def test_explicit_data_directory_and_missing_csv(self):
        self.assertEqual(load_osd575(data_dir=str(DEFAULT_DATA_DIR)), self.rows)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError) as error:
                load_osd575(data_dir=Path(directory))
            self.assertEqual(Path(error.exception.filename).parent, Path(directory))
            self.assertEqual(Path(error.exception.filename).name, self.rows[0].source.file)

    def test_reports_path_and_line_for_malformed_row(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / self.rows[0].source.file
            path.write_text(
                "Sample Name,example_value,example_range_min,example_range_max\n"
                "C001_serum_L-3,1,0\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError) as error:
                load_osd575_panel(directory, "cmp")
        self.assertIn(f"{path}:2: row does not match CSV headers", str(error.exception))

    def test_rejects_duplicate_sample_within_panel(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / self.rows[0].source.file
            path.write_text(
                "Sample Name,example_value,example_range_min,example_range_max\n"
                "C001_serum_L-3,1,0,1\n"
                "C001_serum_L-3,2,0,1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate sample ID"):
                load_osd575_panel(directory, "cmp")


if __name__ == "__main__":
    unittest.main()
