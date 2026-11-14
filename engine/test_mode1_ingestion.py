import csv
import io
import json
import os
import socket
import tempfile
import unittest
from collections import Counter
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from engine.mode1_contracts import validate_assessment, validate_manual_check_in
from engine.mode1_ingestion import (
    DEFAULT_DATA_PATH,
    load_evaluation_labels,
    load_monitoring_data,
    select_series,
    serialize_observation,
)

APOLLO = "apollo10_heart_rate"
SOYUZ = "apollo_soyuz_inflight_vitals"
SKYLAB = "skylab4_inflight_exercise"
EXAMPLES = Path(__file__).with_name("mode1_examples")


def csv_name(stem):
    return f"{stem}_iss_synthetic.csv"


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(os.environ.get("CREW_HEALTH_MODE1_DATA", DEFAULT_DATA_PATH))
        if not cls.source.exists():
            if "CREW_HEALTH_MODE1_DATA" in os.environ:
                raise FileNotFoundError(cls.source)
            raise unittest.SkipTest("Synthetic dataset unavailable. Set CREW_HEALTH_MODE1_DATA.")
        cls.records = load_monitoring_data(cls.source)

    def test_covers_all_rows_crew_and_contexts(self):
        rows = self.records
        self.assertEqual(Counter(row.source_file for row in rows),
                         {csv_name(APOLLO): 600, csv_name(SOYUZ): 600, csv_name(SKYLAB): 1800})
        self.assertEqual(Counter(row.astronaut_id for row in rows), {
            "commander": 750, "flight_engineer_1": 750,
            "flight_engineer_2": 750, "flight_engineer_3": 750,
        })
        self.assertEqual(len({row.timestamp for row in rows}), 3000)
        self.assertEqual(len({row.mission_day for row in rows}), 150)
        self.assertEqual(Counter(reading.value_status for row in rows for reading in row.readings),
                         {"valid": 13200})
        self.assertEqual([row.timestamp for row in rows], sorted(row.timestamp for row in rows))
        self.assertEqual(Counter(row.activity_context for row in rows), {
            "morning_check": 600, "inflight_vitals_check": 600,
            "rest": 600, "exercise": 600, "recovery": 600,
        })

    def test_source_mapping_units_and_chronological_series(self):
        first = self.records[0]
        self.assertEqual((first.astronaut_id, first.source_file, first.source_row, first.mission_day),
                         ("commander", csv_name(APOLLO), 1, 1))
        self.assertEqual(first.timestamp.isoformat(), "2030-01-01T07:00:00+00:00")
        self.assertEqual(first.readings[0].raw_value, "79")
        units = {r.kind: r.unit for row in self.records for r in row.readings}
        self.assertEqual(units["respiratory_rate_breaths_per_min"], "breaths/min")
        self.assertEqual(units["minute_ventilation_mean_l_min_btps"], "L/min BTPS")
        self.assertEqual(units["oxygen_uptake_mean_l_min_stpd"], "L/min STPD")
        self.assertEqual(units["carbon_dioxide_output_mean_l_min_stpd"], "L/min STPD")
        self.assertEqual(units["systolic_bp_mean_mmhg"], "mmHg")
        series = select_series(reversed(self.records), astronaut_id="commander",
                               source_file=csv_name(SKYLAB), kind="heart_rate_mean_bpm",
                               activity_context="recovery")
        self.assertEqual(len(series), 150)
        stamps = [row.timestamp for row, _ in series]
        self.assertEqual(stamps, sorted(stamps))
        self.assertTrue(all(row.source_context == "post_exercise_recovery" for row, _ in series))

    def test_evaluation_labels_are_separate_and_loading_is_offline(self):
        blocked = OSError("network disabled")
        with patch.object(socket, "getaddrinfo", side_effect=blocked), patch.object(
            socket.socket, "connect", side_effect=blocked
        ):
            labels = load_evaluation_labels(self.source)
            monitoring = load_monitoring_data(self.source)
        self.assertEqual(monitoring, self.records)
        self.assertEqual(Counter(row.expected_scenario_severity for row in labels),
                         {"normal": 2905, "mild": 92, "critical": 3})
        self.assertEqual({(row.source_file, row.source_row) for row in labels},
                         {(row.source_file, row.source_row) for row in monitoring})
        soyuz = next(row for row in monitoring if row.source_file == csv_name(SOYUZ))
        self.assertIsNone(soyuz.source_context)
        self.assertEqual(soyuz.activity_context, "inflight_vitals_check")
        self.assertEqual(next(row for row in labels if row.source_file == soyuz.source_file
                              and row.source_row == soyuz.source_row).source_context, "high_workload_check")
        payload = json.dumps([serialize_observation(row) for row in monitoring], allow_nan=False)
        for label in ("expected_scenario_severity", "scenario", "high_workload_check", "delayed_recovery"):
            self.assertNotIn(label, payload)


class FixtureTests(unittest.TestCase):
    def make_zip(self, path, *, mapping=(2, 1), valid_profiles=True, valid_timeline=True):
        crew = [{"role": "commander", "pulseRole": "Commander"}] if valid_profiles else None
        profiles = {"data_origin": "synthetic", "crew": crew}
        schemas = {
            APOLLO: (
                ["crew_role", "mission_event", "heart_rate_bpm"],
                [["Commander", "Morning health check", "NA"], ["Commander", "Morning health check", "NaN"]],
            ),
            SOYUZ: (
                ["crew_role", "activity_context", "mission_day", "heart_rate_mean_bpm",
                 "heart_rate_peak_bpm", "respiratory_rate_breaths_per_min"],
                [["commander", "routine_check", 1, 70, 80, 15]],
            ),
            SKYLAB: (
                ["crew_role", "activity_context", "heart_rate_mean_bpm", "systolic_bp_mean_mmhg",
                 "diastolic_bp_mean_mmhg", "minute_ventilation_mean_l_min_btps",
                 "oxygen_uptake_mean_l_min_stpd", "carbon_dioxide_output_mean_l_min_stpd"],
                [["commander", "rest", 70, 110, 70, "11.88", "0.3", "0.29"]],
            ),
        }
        with ZipFile(path, "w") as archive:
            archive.writestr("bundle/crew_profiles.json", json.dumps(profiles))
            for hour, (stem, (header, rows)) in enumerate(schemas.items(), start=7):
                buffer = io.StringIO(newline="")
                writer = csv.writer(buffer)
                writer.writerow(header)
                writer.writerows(rows)
                archive.writestr(f"bundle/{csv_name(stem)}", buffer.getvalue())
                timeline = [
                    {"crew_role": "commander", "mission_day": 1, "csv_row": number,
                     "timestamp_utc": f"2030-01-01T0{hour}:0{3 - i}:00Z"}
                    for i, number in enumerate(mapping if stem == APOLLO else (1,))
                ]
                archive.writestr(f"bundle/{stem}_timeline.json", json.dumps({
                    "csv": csv_name(stem), "data_origin": "synthetic",
                    "timeline": timeline if valid_timeline else [None],
                }))

    def test_joins_source_rows_before_sorting_and_marks_missing_and_invalid(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "data.zip"
            self.make_zip(path)
            first, second, *_ = load_monitoring_data(path)
        self.assertEqual((first.source_row, first.timestamp.minute), (1, 2))
        self.assertEqual((second.source_row, second.timestamp.minute), (2, 3))
        self.assertEqual(first.readings[0].value_status, "missing")
        self.assertEqual(second.readings[0].value_status, "invalid")
        self.assertIsNone(serialize_observation(second)["readings"][0]["value"])

    def test_rejects_duplicate_missing_and_unmatched_timeline_mappings(self):
        for mapping, error in (((1, 1), "duplicate"), ((1,), "missing timeline"), ((1, 2, 3), "unmatched")):
            with self.subTest(mapping=mapping), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "data.zip"
                self.make_zip(path, mapping=mapping)
                with self.assertRaisesRegex(ValueError, error):
                    load_monitoring_data(path)

    def test_reports_malformed_profile_and_timeline_metadata(self):
        for option, filename in (("valid_profiles", "crew_profiles.json"),
                                 ("valid_timeline", "apollo10_heart_rate_timeline.json")):
            with self.subTest(option=option), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "data.zip"
                self.make_zip(path, **{option: False})
                with self.assertRaisesRegex(ValueError, filename):
                    load_monitoring_data(path)


class ContractTests(unittest.TestCase):
    def test_manual_contract_optional_indicators_and_json(self):
        request = json.loads((EXAMPLES / "manual_check_in.json").read_text(encoding="utf-8"))
        validated = validate_manual_check_in(request)
        self.assertEqual(validated["indicators"]["mood"], "good")
        self.assertEqual(validated["indicators"]["sleep_duration"]["value"], "7.5")
        request["indicators"]["sleep_duration"] = None
        del request["indicators"]["mood"]
        payload = json.loads(json.dumps(validate_manual_check_in(request), allow_nan=False))
        self.assertNotIn("sleep_duration", payload["indicators"])
        self.assertNotIn("mood", payload["indicators"])
        self.assertEqual(payload["data_origin"], "user")

    def test_manual_contract_rejects_wrong_units_invalid_value_and_origin(self):
        request = json.loads((EXAMPLES / "manual_check_in.json").read_text(encoding="utf-8"))
        for value, unit in ((True, "bpm"), ("NaN", "bpm"), ("72", "L/min"), ("-1", "bpm")):
            with self.subTest(value=value, unit=unit):
                invalid = deepcopy(request)
                invalid["indicators"]["heart_rate"] = {"value": value, "unit": unit}
                with self.assertRaises(ValueError):
                    validate_manual_check_in(invalid)
        with self.assertRaises(ValueError):
            validate_manual_check_in({**request, "data_origin": "NASA"})

    def test_manual_contract_rejects_invalid_timestamp_offset(self):
        request = json.loads((EXAMPLES / "manual_check_in.json").read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "timestamp"):
            validate_manual_check_in({**request, "timestamp": "2030-01-01T07:00:00+00:60"})

    def test_assessment_fixture_serializes_and_warning_requires_rule_and_protocol(self):
        response = json.loads((EXAMPLES / "mock_assessment.json").read_text(encoding="utf-8"))
        payload = json.loads(json.dumps(validate_assessment(response), allow_nan=False))
        self.assertTrue(payload["mock"])
        self.assertEqual(payload["overall_status"], "insufficient_data")
        self.assertIsNone(payload["evidence"][0]["baseline"])
        with self.assertRaises(ValueError):
            validate_assessment({**response, "overall_status": "rule_supported_warning"})
