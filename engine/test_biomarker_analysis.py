import json
import random
import unittest
from dataclasses import replace
from decimal import Decimal, localcontext

from engine.biomarker_analysis import (
    analyze_postflight,
    compare_lab_interval,
    group_measurements,
    serialize_analysis,
)
from engine.nasa_ingestion import CsvSource, SerumMeasurement, load_osd575


def measurement(day, raw, *, crew="C001", biomarker="example", unit="mg/dL"):
    visit = f"L{day}" if day < 0 else f"R{day:+}"
    value = None if raw in {"", "NA", "bad"} else Decimal(raw)
    return SerumMeasurement(
        crew_id=crew,
        visit=visit,
        phase="preflight" if day < 0 else "postflight",
        phase_day=day,
        source_sample_id=f"{crew}_serum_{visit}",
        group="metabolic",
        panel="cmp",
        biomarker=biomarker,
        value=value,
        unit=unit,
        lab_ref_min=None,
        lab_ref_max=None,
        normalized_percent=None,
        raw_value=raw,
        raw_lab_ref_min=None,
        raw_lab_ref_max=None,
        raw_normalized_percent=None,
        source=CsvSource("fixture.csv", 2, "example_value"),
    )


class NASAAnalysisIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.measurements = load_osd575()
        cls.results = analyze_postflight(cls.measurements)
        cls.by_key = {
            (row.crew_id, row.panel, row.biomarker, row.visit): row for row in cls.results
        }

    def test_glucose_handoff_examples(self):
        cases = [
            ("C001", "R+1", (83, 80, 69), 90, "77.33", "12.67", "within", "increase"),
            ("C002", "R+45", (69, 72, 78), 44, "73.00", "-29.00", "below", "decrease"),
            ("C003", "R+1", (77, 62, 75), 103, "71.33", "31.67", "above", "increase"),
        ]
        series = group_measurements(self.measurements)
        for crew, visit, history, current, baseline, delta, lab, direction in cases:
            with self.subTest(crew=crew, visit=visit):
                ordered = sorted(series[crew, "cmp", "glucose"], key=lambda row: row.phase_day)
                preflight_values = tuple(
                    row.value for row in ordered if row.phase == "preflight"
                )
                self.assertEqual(preflight_values, history)
                row = self.by_key[crew, "cmp", "glucose", visit]
                self.assertEqual(row.baseline_sample_count, 3)
                self.assertEqual(row.baseline_status, "complete")
                self.assertEqual(row.current_value, Decimal(current))
                self.assertEqual(format(row.baseline_value, ".2f"), baseline)
                self.assertEqual(format(row.absolute_change, ".2f"), delta)
                self.assertEqual(row.change_direction, direction)
                self.assertEqual((row.lab_ref_min, row.lab_ref_max), (Decimal("65"), Decimal("99")))
                self.assertEqual((row.lab_comparison, row.interval_coverage), (lab, "two_sided"))

    def test_insufficient_glucose_history_and_configurable_minimum(self):
        rows = [row for row in self.measurements
                if (row.crew_id, row.panel, row.biomarker) == ("C001", "cmp", "glucose")
                and row.visit != "L-3"]
        row = analyze_postflight(rows)[0]
        self.assertEqual((row.visit, row.baseline_sample_count), ("R+1", 2))
        self.assertEqual(row.baseline_status, "insufficient_baseline")
        self.assertIsNone(row.absolute_change)
        self.assertEqual(row.lab_comparison, "within")
        self.assertEqual(analyze_postflight(rows, min_preflight=2)[0].baseline_value, Decimal("81.5"))

    def test_all_postflight_rows_and_series_are_represented(self):
        def key(row):
            return row.crew_id, row.panel, row.biomarker, row.visit

        expected = {key(row): row for row in self.measurements if row.phase == "postflight"}
        self.assertEqual(self.by_key.keys(), expected.keys())
        self.assertEqual(len(self.by_key), len(self.results))
        self.assertEqual({row.crew_id for row in self.results}, {"C001", "C002", "C003", "C004"})
        self.assertEqual({row.panel for row in self.results},
                         {"cmp", "eve_cardiovascular", "eve_immune", "alamar_immune"})
        for result in self.results:
            original = expected[key(result)]
            self.assertEqual(result.source, original.source)
            self.assertEqual(result.unit, original.unit)

    def test_alamar_missing_visit_and_assay_scale(self):
        row = self.by_key["C003", "alamar_immune", "activin_a", "R+1"]
        self.assertEqual(row.baseline_status, "insufficient_baseline")
        self.assertEqual(row.baseline_sample_count, 2)
        self.assertNotIn("C003_serum_L-44", row.valid_preflight_sample_ids)
        self.assertEqual(row.unit, "NPQ")
        self.assertIn("original assay scale", " ".join(row.analysis_notes))
        self.assertEqual((row.lab_comparison, row.interval_coverage), ("unavailable", "none"))

    def test_order_and_decimal_context_do_not_change_results(self):
        reordered = list(self.measurements)
        random.Random(42).shuffle(reordered)
        with localcontext() as context:
            context.prec = 6
            self.assertEqual(analyze_postflight(iter(reordered)), self.results)

    def test_json_serialization_keeps_precision_and_traceability(self):
        row = self.by_key["C001", "cmp", "glucose", "R+1"]
        data = json.loads(json.dumps(serialize_analysis(row), allow_nan=False))
        self.assertEqual(Decimal(data["baseline_value"]), row.baseline_value)
        self.assertEqual(Decimal(data["percentage_change"]), row.percentage_change)
        self.assertEqual(data["current_value"], "90")
        self.assertEqual(data["study_id"], "OSD-575")
        self.assertEqual(data["provenance"], "dataset:OSD-575")
        self.assertEqual(data["source"]["row"], row.source.row)
        self.assertEqual(data["valid_preflight_sample_ids"], list(row.valid_preflight_sample_ids))
        immune = self.by_key["C003", "alamar_immune", "activin_a", "R+1"]
        self.assertIsNone(json.loads(json.dumps(serialize_analysis(immune)))["baseline_value"])


class BiomarkerAnalysisTests(unittest.TestCase):
    def test_missing_invalid_and_nonfinite_readings(self):
        rows = [measurement(-7, ""), measurement(-5, "bad"), measurement(-4, "Infinity"),
                measurement(-3, "10"), measurement(-2, "10"), measurement(-1, "10"),
                measurement(1, "NA"), measurement(2, "NaN")]
        for result, status in zip(analyze_postflight(rows), ("missing", "invalid"), strict=True):
            self.assertEqual(result.current_value_status, status)
            self.assertEqual(result.baseline_value, Decimal("10"))
            self.assertEqual(result.baseline_sample_count, 3)
            self.assertEqual(result.missing_preflight_sample_ids, ("C001_serum_L-7",))
            self.assertEqual(result.invalid_preflight_sample_ids, ("C001_serum_L-5", "C001_serum_L-4"))
            self.assertEqual(result.change_direction, "unavailable")
            self.assertIsNone(result.absolute_change)
            self.assertIsNone(result.percentage_change)
            self.assertIn(f"Current measurement is {status}.", result.analysis_notes)

    def test_zero_baseline_and_unchanged(self):
        rows = [measurement(-3, "-1"), measurement(-2, "0"), measurement(-1, "1"),
                measurement(1, "2"), measurement(2, "0")]
        increased, same = analyze_postflight(rows)
        self.assertEqual(increased.baseline_value, Decimal("0"))
        self.assertEqual(increased.absolute_change, Decimal("2"))
        self.assertIsNone(increased.percentage_change)
        self.assertEqual(same.change_direction, "unchanged")

    def test_preserves_small_changes_on_a_high_precision_baseline(self):
        baseline = "123456789012345678901234567890.1234567890"
        rows = [
            measurement(-3, baseline),
            measurement(-2, baseline),
            measurement(-1, baseline),
            measurement(1, "123456789012345678901234567890.1234567891"),
        ]
        row, = analyze_postflight(rows)
        self.assertEqual(row.baseline_value, Decimal(baseline))
        self.assertEqual(row.absolute_change, Decimal("0.0000000001"))
        self.assertEqual(row.change_direction, "increase")

    def test_no_postflight_leakage_or_cross_series_mixing(self):
        rows = [measurement(-3, "10"), measurement(-2, "10"), measurement(-1, "10"),
                measurement(1, "20"), measurement(2, "1000"),
                measurement(-1, "90", crew="C002"), measurement(1, "7", crew="C002"),
                measurement(-1, "80", biomarker="other"), measurement(1, "8", biomarker="other"),
                replace(measurement(-1, "60"), panel="eve_immune"),
                replace(measurement(1, "6"), panel="eve_immune")]
        results = analyze_postflight(rows)
        valid = [row for row in results if row.baseline_status == "complete"]
        self.assertEqual(len(valid), 2)
        self.assertEqual({row.baseline_value for row in valid}, {Decimal("10")})
        self.assertEqual(valid[0].percentage_change, Decimal("100"))
        self.assertEqual([row.baseline_sample_count for row in results if row.baseline_value is None],
                         [1, 1, 1])

    def test_lab_limits_use_exact_observation(self):
        cases = [
            ("10", "20", None, None, "within", "two_sided"),
            ("0", "10", None, None, "within", "two_sided"),
            ("11", None, None, "N/A", "below", "lower_only"),
            ("10", None, None, "N/A", "within", "lower_only"),
            (None, "9", "", None, "above", "upper_only"),
            (None, "10", "", None, "within", "upper_only"),
            (None, None, None, None, "unavailable", "none"),
            ("12", "8", None, None, "unavailable", "invalid"),
            (None, "20", "broken", None, "unavailable", "invalid"),
            ("Infinity", "20", None, None, "unavailable", "invalid"),
        ]
        for lower, upper, raw_min, raw_max, comparison, coverage in cases:
            with self.subTest(lower=lower, upper=upper, raw_min=raw_min):
                row = replace(
                    measurement(1, "10"),
                    lab_ref_min=Decimal(lower) if lower is not None else None,
                    lab_ref_max=Decimal(upper) if upper is not None else None,
                    raw_lab_ref_min=raw_min,
                    raw_lab_ref_max=raw_max,
                )
                self.assertEqual(compare_lab_interval(row), (comparison, coverage))
                missing = replace(row, value=None, raw_value="")
                self.assertEqual(compare_lab_interval(missing), ("unavailable", coverage))

    def test_incompatible_units_keep_laboratory_comparison_available(self):
        rows = [measurement(-3, "10"), measurement(-2, "10"), measurement(-1, "10"),
                replace(measurement(1, "5", unit="mmol/L"), lab_ref_min=Decimal("5"))]
        row, = analyze_postflight(rows)
        self.assertEqual(row.baseline_status, "incompatible_units")
        self.assertIsNone(row.absolute_change)
        self.assertEqual(row.lab_comparison, "within")

    def test_rejects_duplicate_samples_and_invalid_minimum(self):
        row = measurement(1, "10")
        with self.assertRaisesRegex(ValueError, "Duplicate sample ID"):
            analyze_postflight([row, row])
        for minimum in (0, -1, True, 2.5):
            with self.subTest(minimum=minimum), self.assertRaisesRegex(ValueError, "positive integer"):
                analyze_postflight([row], min_preflight=minimum)
