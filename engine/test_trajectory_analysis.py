import json
import random
import unittest
from dataclasses import replace
from decimal import Decimal, localcontext

from engine.biomarker_analysis import analyze_postflight
from engine.nasa_ingestion import load_osd575
from engine.trajectory_analysis import (
    analyze_trajectories,
    compare_astronauts,
    serialize_trajectory,
)
from engine.test_biomarker_analysis import measurement


def trajectory_for(*postflight, preflight=("10", "10", "10")):
    rows = [measurement(-day, raw) for day, raw in enumerate(preflight, start=1)]
    rows.extend(measurement(day, raw) for day, raw in postflight)
    trajectory, = analyze_trajectories(analyze_postflight(rows))
    return trajectory


class TrajectoryTests(unittest.TestCase):
    def test_closer_farther_mixed_and_unchanged(self):
        cases = [
            (("17", "14", "10"), "consistently_closer", ("closer", "closer"), "-7"),
            (("9", "7", "5"), "consistently_farther", ("farther", "farther"), "4"),
            (("15", "13", "17"), "mixed", ("closer", "farther"), "2"),
            (("14", "14", "12"), "mixed", ("unchanged", "closer"), "-2"),
            (("14", "6", "14"), "unchanged_distance", ("unchanged", "unchanged"), "0"),
        ]
        for values, classification, movements, distance_change in cases:
            with self.subTest(values=values):
                row = trajectory_for(*zip((1, 45, 82), values, strict=True))
                self.assertEqual(row.trajectory_classification, classification)
                self.assertEqual(
                    tuple(visit.distance_movement for visit in row.visits[1:]), movements
                )
                self.assertEqual(row.first_to_last_distance_change, Decimal(distance_change))

    def test_crossing_through_an_observation_equal_to_baseline(self):
        row = trajectory_for((1, "12"), (45, "10"), (82, "9"))
        self.assertTrue(row.crossed_baseline)
        self.assertEqual(
            [visit.position_relative_to_baseline for visit in row.visits],
            ["above", "equal", "below"],
        )
        self.assertEqual([visit.change_direction for visit in row.visits],
                         ["unavailable", "decrease", "decrease"])
        self.assertFalse(row.measurement_direction_reversed)
        reversed_row = trajectory_for((1, "12"), (45, "10"), (82, "11"))
        self.assertTrue(reversed_row.measurement_direction_reversed)
        self.assertIsNone(trajectory_for((1, "12"), (45, "11")).measurement_direction_reversed)

    def test_gap_handling_preserves_irregular_elapsed_days(self):
        row = trajectory_for((194, "12"), (82, "bad"), (1, "20"), (45, "NA"))
        self.assertEqual([visit.phase_day for visit in row.visits], [1, 45, 82, 194])
        self.assertEqual((row.valid_observation_count, row.missing_observation_count,
                          row.invalid_observation_count), (2, 1, 1))
        self.assertEqual((row.first_observation.value, row.last_observation.value),
                         (Decimal("20"), Decimal("12")))
        self.assertEqual(row.visits[-1].previous_valid_phase_day, 1)
        self.assertEqual(row.visits[-1].days_since_previous_valid, 193)
        self.assertEqual(row.visits[-1].distance_movement, "closer")
        self.assertIsNone(row.visits[1].distance_movement)
        self.assertIn("Limited evidence", " ".join(row.evidence_limitations))

        absent = trajectory_for((1, "20"), (45, "12"), (194, "11"))
        self.assertEqual(absent.absent_visit_days, (82,))
        self.assertEqual(absent.missing_observation_count, 0)
        self.assertEqual(absent.visits[-1].days_since_previous_valid, 149)

    def test_incomplete_baseline_or_too_few_observations(self):
        no_baseline = trajectory_for((1, "18"), (45, "12"), preflight=("10", "10"))
        self.assertEqual(no_baseline.baseline_status, "insufficient_baseline")
        self.assertEqual(no_baseline.trajectory_classification, "insufficient_data")
        self.assertIsNone(no_baseline.visits[0].distance_from_baseline)
        self.assertEqual(no_baseline.first_observation.value, Decimal("18"))
        for first, last in (("NA", "11"), ("bad", "NA")):
            with self.subTest(first=first, last=last):
                row = trajectory_for((1, first), (45, last))
                self.assertEqual(row.trajectory_classification, "insufficient_data")
                self.assertIsNone(row.crossed_baseline)
                self.assertIsNone(row.first_to_last_distance_change)
                expected = Decimal("11") if last == "11" else None
                observed = row.last_observation.value if row.last_observation else None
                self.assertEqual(observed, expected)

    def test_rejects_mixed_units_and_duplicate_days(self):
        rows = [measurement(day, "10") for day in (-3, -2, -1, 1, 45)]
        first, last = analyze_postflight(rows)
        with self.assertRaisesRegex(ValueError, "Incompatible units"):
            analyze_trajectories([first, replace(last, unit="mmol/L")])
        with self.assertRaisesRegex(ValueError, "Duplicate postflight day"):
            analyze_trajectories([first, first])
        trajectory, = analyze_trajectories([first, last])
        other = replace(trajectory, crew_id="C002", unit="mmol/L")
        with self.assertRaisesRegex(ValueError, "Incompatible units"):
            compare_astronauts([trajectory, other], panel="cmp", biomarker="example")


class NASATrajectoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comparisons = analyze_postflight(load_osd575())
        cls.trajectories = analyze_trajectories(cls.comparisons)

    def test_preserves_all_astronauts_panels_and_observations(self):
        self.assertEqual({row.crew_id for row in self.trajectories}, {"C001", "C002", "C003", "C004"})
        self.assertEqual({row.panel for row in self.trajectories},
                         {"cmp", "eve_cardiovascular", "eve_immune", "alamar_immune"})
        originals = {
            (row.crew_id, row.panel, row.biomarker, row.source_sample_id): row
            for row in self.comparisons
        }
        for series in self.trajectories:
            self.assertEqual(series.study_id, "OSD-575")
            self.assertEqual(series.provenance, "dataset:OSD-575")
            self.assertEqual([visit.phase_day for visit in series.visits], [1, 45, 82, 194])
            for visit in series.visits:
                original = originals.pop((series.crew_id, series.panel, series.biomarker,
                                          visit.source_sample_id))
                self.assertEqual(visit.source, original.source)
                self.assertEqual(visit.lab_comparison, original.lab_comparison)
                self.assertEqual(visit.change_from_baseline, original.absolute_change)
                self.assertEqual(visit.value, original.current_value)
                self.assertEqual(series.baseline_value, original.baseline_value)
        self.assertFalse(originals)

    def test_cmp_glucose_comparison_keeps_personal_baselines_separate(self):
        glucose = compare_astronauts(reversed(self.trajectories), panel="cmp", biomarker="glucose")
        self.assertEqual([row.crew_id for row in glucose], ["C001", "C002", "C003", "C004"])
        self.assertEqual({(row.panel, row.biomarker, row.unit) for row in glucose},
                         {("cmp", "glucose", "mg/dL")})
        self.assertEqual([format(row.baseline_value, ".2f") for row in glucose],
                         ["77.33", "73.00", "71.33", "79.67"])
        self.assertEqual([row.first_observation.value for row in glucose], [90, 83, 103, 97])

    def test_alamar_missing_preflight_sample(self):
        rows = compare_astronauts(self.trajectories, panel="alamar_immune", biomarker="activin_a")
        row = next(row for row in rows if row.crew_id == "C003")
        self.assertEqual(row.unit, "NPQ")
        self.assertEqual(row.valid_preflight_sample_ids, ("C003_serum_L-92", "C003_serum_L-3"))
        self.assertEqual(row.baseline_sample_count, 2)
        self.assertEqual(row.valid_observation_count, 4)
        self.assertEqual(row.trajectory_classification, "insufficient_data")

    def test_deterministic_order_and_strict_json(self):
        reordered = list(self.comparisons)
        random.Random(8).shuffle(reordered)
        with localcontext() as context:
            context.prec = 5
            self.assertEqual(analyze_trajectories(reordered), self.trajectories)
        payload = json.loads(json.dumps(
            [serialize_trajectory(row) for row in self.trajectories], allow_nan=False
        ))
        row = next(row for row in payload if row["crew_id"] == "C001" and row["biomarker"] == "glucose")
        self.assertEqual(row["visits"][0]["value"], "90")
        self.assertEqual(row["visits"][0]["source"]["row"], 5)
        self.assertIsNone(row["visits"][0]["days_since_previous_valid"])
