import csv
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.radiation_history import (
    DATASET_ID,
    DEFAULT_CSV_PATH,
    EVENT_URL,
    load_radiation_history,
    may_20_event_summary,
    radiation_timeline,
)

_HEADER = ["timestamp_utc", "absorbed_dose_rate_ugy_per_day", "detector", "nasa_cdf_url"]
_CDF = (
    "https://cdaweb.gsfc.nasa.gov/sp_phys/data/msl/rad/cdf/obs-l2/2024/"
    "msl_rad_obs-l2_2024141_v04.cdf"
)


class RadiationHistoryTests(unittest.TestCase):
    def fixture(self, rows, header=_HEADER):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        path = Path(folder) / "rad.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        return path

    def test_validation_rejects_bad_headers_timestamps_provenance_and_duplicates(self):
        valid = ("2024-05-20T00:00:00Z", "10", "E", _CDF)
        cases = [
            (self.fixture([valid], header=_HEADER[:3]), "expected CSV columns"),
            (self.fixture([valid[:-1]]), "does not match CSV headers"),
            (self.fixture([("2024-05-20T00:00:00+01:00", *valid[1:])]), "expected an ISO"),
            (self.fixture([("2024-02-31T00:00:00Z", *valid[1:])]), "invalid UTC timestamp"),
            (self.fixture([(*valid[:3], "https://example.net/file.cdf")]), "invalid NASA"),
            (self.fixture([valid, ("2024-05-20T00:00:00+00:00", *valid[1:])]), "duplicate"),
        ]
        for path, error in cases:
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                load_radiation_history(path)

    def test_sorts_preserves_source_and_separates_detectors(self):
        path = self.fixture([
            ("2024-05-20T02:00:00Z", "15.00", "E", _CDF),
            ("2024-05-19T01:00:00.000Z", "220", "B", _CDF),
            ("2024-05-20T03:50:00Z", "9", "E", _CDF),
            ("2024-05-19T01:00:00.000Z", "12", "E", _CDF),
        ])
        history = load_radiation_history(path)
        result = radiation_timeline(history, include_statistics=True)
        self.assertEqual((result["dataset_id"], result["unit"]), (DATASET_ID, "µGy/day"))
        b, e = result["series"]
        self.assertEqual((b["detector"], e["detector"]), ("B", "E"))
        self.assertEqual(b["statistics"]["median"], "220")
        self.assertIsNone(b["statistics"]["first_to_last_change"])
        self.assertEqual([point["source_line"] for point in e["observations"]], [5, 2, 4])
        self.assertEqual(e["observations"][1]["value"], "15.00")
        self.assertEqual(e["start_timestamp_utc"], "2024-05-19T01:00:00.000Z")
        stats = e["statistics"]
        self.assertEqual((stats["min"], stats["max"], stats["median"], stats["first_to_last_change"]),
                         ("9", "15.00", "12", "-3"))
        self.assertEqual(stats["peak"], e["observations"][1])
        self.assertEqual(stats["mean"], "12.00")

    def test_date_and_detector_filters_preserve_gaps_and_invalid_cells(self):
        path = self.fixture([
            ("2024-05-18T23:59:59Z", "10", "E", _CDF),
            ("2024-05-20T00:00:00Z", "NA", "E", _CDF),
            ("2024-05-20T12:00:00Z", "NaN", "E", _CDF),
            ("2024-05-20T22:00:00Z", "-1", "E", _CDF),
            ("2024-05-20T23:59:59Z", "0", "E", _CDF),
            ("2024-05-21T00:00:00Z", "30", "E", _CDF),
            ("2024-05-20T17:00:00Z", "200", "B", _CDF),
        ])
        history = load_radiation_history(path)
        filtered = radiation_timeline(history, start_date="2024-05-19", end_date="2024-05-20",
                                      detector="E", include_statistics=True)
        e, = filtered["series"]
        self.assertEqual([point["value_status"] for point in e["observations"]],
                         ["missing", "invalid", "invalid", "valid"])
        self.assertEqual([point["value"] for point in e["observations"]], [None, None, None, "0"])
        self.assertEqual(e["statistics"]["valid_count"], 1)
        self.assertEqual(e["statistics"]["missing_count"], 1)
        self.assertEqual(e["statistics"]["invalid_count"], 2)
        self.assertEqual(e["statistics"]["peak"]["value"], "0")
        self.assertIsNone(radiation_timeline(history)["series"][0]["statistics"])
        for options in ({"start_date": "20240520"}, {"start_date": "2024-05-21", "end_date": "2024-05-20"},
                        {"detector": "Z"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                radiation_timeline(history, **options)

    def test_event_without_local_evidence_or_a_complete_prior_week(self):
        history = load_radiation_history(self.fixture([
            ("2024-05-19T12:00:00Z", "15", "E", _CDF),
            ("2024-05-20T12:00:00Z", "N/A", "E", _CDF),
        ]))
        result = may_20_event_summary(history)
        self.assertEqual(result["source_reference"], EVENT_URL)
        self.assertFalse(result["evidence_available"])
        e, = result["series"]
        self.assertIsNone(e["statistics"]["peak"])
        self.assertIsNone(e["preceding_week_comparison"]["median"])
        self.assertEqual(e["preceding_week_comparison"]["observed_date_count"], 1)
        self.assertEqual(json.loads(json.dumps(result, allow_nan=False)), result)


class NASAFileTests(unittest.TestCase):
    def test_real_coverage_event_and_offline_serialization(self):
        path = Path(os.environ.get("CREW_HEALTH_RAD_CSV", DEFAULT_CSV_PATH))
        if not path.is_file() and "CREW_HEALTH_RAD_CSV" not in os.environ:
            self.skipTest("RAD dataset unavailable. Set CREW_HEALTH_RAD_CSV.")
        blocked = OSError("network disabled")
        with patch.object(socket, "getaddrinfo", side_effect=blocked), patch.object(
            socket.socket, "connect", side_effect=blocked
        ):
            history = load_radiation_history(path)
            timeline = radiation_timeline(history, include_statistics=True)
            event = may_20_event_summary(history, detector="E")
        self.assertEqual(timeline["observation_count"], 5971)
        e, = timeline["series"]
        self.assertEqual(e["detector"], "E")
        self.assertEqual(e["start_timestamp_utc"], "2024-03-07T00:14:58.000Z")
        self.assertEqual(e["end_timestamp_utc"], "2024-05-20T23:56:36.000Z")
        self.assertEqual(e["statistics"]["valid_count"], 5971)
        self.assertEqual(len({point["timestamp_utc"][:10] for point in e["observations"]}), 75)
        self.assertEqual(len({point["nasa_cdf_url"] for point in e["observations"]}), 75)
        self.assertTrue(event["evidence_available"])
        day, = event["series"]
        self.assertEqual(day["observation_count"], 139)
        self.assertEqual(day["statistics"]["median"], "1153.6759")
        peak = day["statistics"]["peak"]
        self.assertEqual((peak["timestamp_utc"], peak["value"], peak["source_line"]),
                         ("2024-05-20T06:15:19.000Z", "8377.913", 5857))
        self.assertEqual(peak["nasa_cdf_url"], _CDF)
        self.assertEqual(day["preceding_week_comparison"]["median"], "148.34653")
        self.assertEqual(day["preceding_week_comparison"]["valid_sample_count"], 579)
        for payload in (timeline, event):
            self.assertEqual(json.loads(json.dumps(payload, allow_nan=False)), payload)
