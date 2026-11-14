import json
import unittest
from dataclasses import replace
from pathlib import Path

from engine.biomarker_analysis import analyze_postflight, serialize_analysis
from engine.biological_passport import build_biological_passport
from engine.nasa_ingestion import STUDY_URL, load_osd575
from engine.trajectory_analysis import analyze_trajectories


class BiologicalPassportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comparisons = analyze_postflight(load_osd575())
        cls.trajectories = analyze_trajectories(cls.comparisons)

    def passport(self, astronaut="C002", visit="R+45", **options):
        return build_biological_passport(
            self.comparisons, self.trajectories, astronaut_id=astronaut,
            selected_visit=visit, **options,
        )

    def test_all_astronauts_visits_and_panels(self):
        for astronaut in ("C001", "C002", "C003", "C004"):
            for visit in ("R+1", "R+45", "R+82", "R+194"):
                with self.subTest(astronaut=astronaut, visit=visit):
                    result = self.passport(astronaut, visit)
                    self.assertEqual((result["astronaut_id"], result["selected_visit"]),
                                     (astronaut, visit))
                    self.assertEqual(result["total_biomarkers_considered"], 302)
                    self.assertEqual(sum(result["measurement_status_counts"].values()), 302)
                    self.assertEqual([
                        (row["panel"], row["group"], row["total_biomarkers_considered"])
                        for row in result["panels"]
                    ], [
                        ("cmp", "metabolic", 19), ("eve_cardiovascular", "cardiovascular", 9),
                        ("eve_immune", "immune", 71), ("alamar_immune", "immune", 203),
                    ])
                    self.assertEqual(sum(result["trajectories"]["classification_counts"].values()), 302)
                    self.assertEqual(json.loads(json.dumps(result, allow_nan=False)), result)

    def test_c002_glucose_and_reference_counts(self):
        result = self.passport()
        self.assertEqual((result["complete_baseline_count"], result["insufficient_baseline_count"]),
                         (301, 1))
        lab = result["lab_interval_summary"]
        self.assertEqual({key: lab[key] for key in ("below", "within", "above", "unavailable")},
                         {"below": 1, "within": 17, "above": 0, "unavailable": 284})
        self.assertEqual(lab["coverage"], {
            "two_sided": 17, "lower_only": 2, "upper_only": 0, "none": 283, "invalid": 0,
        })
        self.assertEqual(result["measurement_status_counts"], {"valid": 301, "missing": 1, "invalid": 0})
        self.assertIn(
            "284 biomarker records have no available laboratory comparison at this visit.",
            result["limitations"],
        )
        finding = result["selected_findings"][0]
        self.assertEqual(finding["category"], "outside_lab_interval")
        self.assertEqual(
            (finding["biomarker"], finding["current_value"], finding["unit"], finding["baseline_value"],
             finding["absolute_change"], finding["lab_comparison"], finding["trajectory_classification"]),
            ("glucose", "44", "mg/dL", "73", "-29", "below", "mixed"),
        )
        self.assertEqual((finding["lab_ref_min"], finding["lab_ref_max"]), ("65", "99"))
        self.assertEqual(result["trajectories"]["scope"], "full_postflight_series")
        self.assertEqual(result["trajectories"]["panels"]["cmp"]["glucose"], "mixed")

    def test_historical_trajectory_scope_distinguishes_later_observations(self):
        at_r45 = self.passport()
        at_r194 = self.passport(visit="R+194")
        historical = at_r45["trajectories"]
        self.assertEqual(historical["label"], "Full historical trajectory")
        self.assertTrue(historical["includes_later_observations"])
        self.assertFalse(at_r194["trajectories"]["includes_later_observations"])
        self.assertEqual(historical["panels"], at_r194["trajectories"]["panels"])
        glucose = at_r45["selected_findings"][0]
        self.assertEqual(glucose["visit"], "R+45")
        self.assertEqual(glucose["trajectory_scope"], "full_postflight_series")

    def test_limitations_and_unavailable_values(self):
        result = self.passport("C003", "R+1")
        alamar = result["panels"][-1]
        self.assertEqual(alamar["insufficient_baseline_count"], 203)
        self.assertEqual(alamar["lab_interval_summary"]["unavailable"], 203)
        self.assertEqual(alamar["lab_interval_summary"]["coverage"]["none"], 203)
        self.assertEqual(alamar["measurement_status_counts"], {"valid": 203, "missing": 0, "invalid": 0})
        self.assertEqual(result["trajectories"]["panels"]["alamar_immune"]["activin_a"], "insufficient_data")
        self.assertTrue(any("204 biomarker records" in note for note in result["limitations"]))

        missing_row = next(row for row in self.comparisons if (
            row.crew_id, row.visit, row.biomarker
        ) == ("C002", "R+82", "bun_to_creatinine_ratio"))
        limited = build_biological_passport([missing_row], astronaut_id="C002", selected_visit="R+82")
        item, = limited["selected_findings"]
        self.assertEqual((item["category"], item["current_value_status"]), ("data_limitation", "missing"))
        self.assertIsNone(item["current_value"])
        self.assertIsNone(item["absolute_change"])
        self.assertIsNone(item["trajectory_classification"])
        self.assertEqual(limited["measurement_status_counts"]["missing"], 1)
        self.assertTrue(any("A3 trajectories were unavailable" in note for note in limited["limitations"]))

    def test_finding_selection_is_deterministic_and_bounded(self):
        expected = self.passport()
        reverse = build_biological_passport(
            reversed(self.comparisons), reversed(self.trajectories),
            astronaut_id="C002", selected_visit="R+45",
        )
        self.assertEqual(reverse, expected)
        self.assertEqual(len(expected["selected_findings"]), 8)
        self.assertEqual(
            [item["category"] for item in expected["selected_findings"]],
            ["outside_lab_interval"] + ["personal_baseline_change"] * 4 + ["longitudinal_pattern"] * 3,
        )
        self.assertEqual(self.passport(max_findings=1)["selected_findings"], expected["selected_findings"][:1])
        self.assertEqual(self.passport(max_findings=0)["selected_findings"], [])

    def test_findings_and_sources_match_upstream(self):
        result = self.passport()
        self.assertEqual(result["study_id"], "OSD-575")
        self.assertEqual(result["data_origin"], "real_nasa_research")
        refs = result["source_references"]
        self.assertEqual(refs["study_url"], STUDY_URL)
        self.assertEqual(len(refs["samples"]), 4)
        expected = {(row.panel, row.biomarker): serialize_analysis(row) for row in self.comparisons
                    if (row.crew_id, row.visit) == ("C002", "R+45")}
        for finding in result["selected_findings"]:
            row = expected[finding["panel"], finding["biomarker"]]
            self.assertEqual({key: finding[key] for key in row}, row)
            self.assertIn({
                "panel": finding["panel"], "file": finding["source"]["file"], "row": finding["source"]["row"],
                "source_sample_id": "C002_serum_R+45", "provenance": "dataset:OSD-575",
            }, refs["samples"])

    def test_rejects_invalid_selection_duplicate_and_inconsistent_results(self):
        with self.assertRaisesRegex(ValueError, "postflight code"):
            self.passport(visit="L-3")
        with self.assertRaises(LookupError):
            self.passport(visit="R+2")
        with self.assertRaises(LookupError):
            self.passport(astronaut="C999")
        row = next(row for row in self.comparisons if (
            row.crew_id, row.visit, row.biomarker
        ) == ("C002", "R+45", "glucose"))
        with self.assertRaisesRegex(ValueError, "Duplicate A2"):
            build_biological_passport([row, row], astronaut_id="C002", selected_visit="R+45")
        trajectory = next(item for item in self.trajectories if (
            item.crew_id, item.panel, item.biomarker
        ) == (row.crew_id, row.panel, row.biomarker))
        with self.assertRaisesRegex(ValueError, "disagree"):
            build_biological_passport([row], [replace(trajectory, unit="wrong")],
                                      astronaut_id="C002", selected_visit="R+45")

    def test_documented_response_matches_live_output(self):
        path = Path(__file__).with_name("biological_passport_examples") / "c002_r45.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), self.passport())
