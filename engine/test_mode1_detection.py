import json
import socket
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from pathlib import Path
from unittest.mock import patch

from engine.mode1_contracts import validate_assessment
from engine.mode1_detection import DetectionConfig, HistoryIndex, assess_check_in, assess_observation
from engine.mode1_ingestion import Observation, Reading

_START = datetime(2030, 1, 1, tzinfo=timezone.utc)
_SKYLAB = "skylab4_inflight_exercise_iss_synthetic.csv"
_SOYUZ = "apollo_soyuz_inflight_vitals_iss_synthetic.csv"
_EXAMPLE = Path(__file__).with_name("mode1_examples") / "manual_check_in.json"


def observation(day, raw, *, astronaut="commander", context="rest", source=_SKYLAB,
                unit="bpm", kind="heart_rate_mean_bpm", status="valid"):
    value = Decimal(raw) if raw is not None else None
    return Observation(
        astronaut, _START + timedelta(days=day), day + 1, context, context,
        source, day + 1, (Reading(kind, unit, value, status, str(raw)),),
    )


def history(values, **kwargs):
    return [observation(day, value, **kwargs) for day, value in enumerate(values)]


def check_in(**updates):
    request = json.loads(_EXAMPLE.read_text(encoding="utf-8"))
    request.pop("data_origin")
    request["timestamp"] = (_START + timedelta(days=20)).isoformat()
    return {**request, **updates}


def indicator(result, name="heart_rate"):
    return next(row for row in result["evidence"] if row["indicator"] == name)


class DetectionTests(unittest.TestCase):
    def test_personal_baselines_produce_different_findings_for_same_value(self):
        rows = history(range(69, 76)) + history(range(59, 66), astronaut="flight_engineer_1")
        index = HistoryIndex(rows)
        request = check_in(astronaut_id="flight_engineer_1")
        request["indicators"]["heart_rate"]["value"] = "74"
        unusual = assess_check_in(request, index)
        normal = assess_check_in({**request, "astronaut_id": "commander"}, index)
        self.assertEqual((normal["overall_status"], unusual["overall_status"]), ("normal", "unusual"))
        self.assertEqual((indicator(normal)["baseline"], indicator(unusual)["baseline"]), ("72", "62"))
        self.assertEqual(unusual["affected_systems"], ["cardiovascular"])
        self.assertEqual(unusual["body_marker"], "chest")
        self.assertIsNone(unusual["next_action_protocol_id"])
        self.assertIsNone(unusual["approved_rule_id"])

    def test_exact_context_unit_source_and_indicator_are_required(self):
        rows = history(range(69, 76))
        rows += history(range(100, 107), context="exercise")
        rows += history(range(100, 107), unit="other")
        rows += history(range(100, 107), source=_SOYUZ)
        rows += history(range(100, 107), kind="heart_rate_peak_bpm")
        rows += history(range(100, 107), astronaut="flight_engineer_1")
        result = assess_check_in(check_in(), HistoryIndex(rows))
        evidence = indicator(result)
        self.assertEqual(evidence["baseline"], "72")
        self.assertEqual(evidence["statistics"]["observation_count"], 7)
        self.assertEqual(indicator(result, "respiratory_rate")["statistics"]["observation_count"], 0)

    def test_median_mad_score_and_strict_threshold(self):
        rows = history([1, 2, 3, 4, 5, 6, 7])
        current = observation(20, "16")
        result = assess_observation(current, HistoryIndex(rows))
        evidence = indicator(result)
        self.assertEqual(evidence["baseline"], "4")
        stats = evidence["statistics"]
        self.assertEqual((stats["mad"], stats["absolute_deviation"], stats["robust_z"]),
                         ("2", "12", "4.0470"))
        self.assertTrue(stats["anomaly"])
        same = assess_observation(current, HistoryIndex(rows),
                                  config=DetectionConfig(anomaly_threshold=Decimal("4.047")))
        self.assertEqual(same["overall_status"], "normal")
        self.assertFalse(indicator(same)["statistics"]["anomaly"])

    def test_zero_and_near_zero_mad_are_indeterminate(self):
        for values in (
            [70] * 7,
            [Decimal("70") + Decimal(i).scaleb(-14) for i in range(7)],
        ):
            with self.subTest(values=values):
                result = assess_observation(observation(20, "70.000000001"), HistoryIndex(history(values)))
                stats = indicator(result)["statistics"]
                self.assertEqual(result["overall_status"], "insufficient_data")
                self.assertIsNone(stats["anomaly"])
                self.assertIsNone(stats["robust_z"])
                self.assertIn("historical MAD", result["insufficient_data"][0])

    def test_unavailable_measurements_and_insufficient_history(self):
        rows = history(range(1, 6))
        rows += [observation(6, None, status="missing"), observation(7, "NaN", status="invalid"),
                 observation(8, "Infinity")]
        result = assess_observation(observation(20, "50"), HistoryIndex(rows))
        self.assertEqual(result["overall_status"], "insufficient_data")
        self.assertEqual(indicator(result)["statistics"]["observation_count"], 5)
        self.assertIsNone(indicator(result)["baseline"])
        missing = assess_observation(observation(20, None, status="missing"),
                                     HistoryIndex(history(range(7))))
        self.assertEqual(indicator(missing)["baseline"], "3")
        self.assertIsNone(indicator(missing)["value"])
        self.assertIn("current value unavailable", missing["insufficient_data"][0])

    def test_rolling_window_excludes_current_and_future_and_sorts_history(self):
        rows = history(range(25))
        rows += [observation(25, "500"), observation(26, "600")]
        current = observation(25, "100")
        result = assess_observation(current, HistoryIndex(reversed(rows)))
        stats = indicator(result)["statistics"]
        self.assertEqual(indicator(result)["baseline"], "17.5")
        self.assertEqual((stats["observation_count"], stats["history_span_days"]), (14, "13.000000"))
        self.assertEqual(result, assess_observation(current, HistoryIndex(rows[:25])))

    def test_theil_sen_uses_elapsed_time_and_stays_descriptive(self):
        rows = [observation(day, 70 + 2 * day) for day in (0, 1, 3, 6, 11, 14, 18)]
        result = assess_observation(observation(20, "90"), HistoryIndex(rows))
        stats = indicator(result)["statistics"]
        self.assertEqual(Decimal(stats["trend_slope_per_day"]), Decimal("2"))
        self.assertEqual(Decimal(stats["history_span_days"]), Decimal("18"))
        self.assertEqual(result["overall_status"], "normal")
        self.assertEqual(result["affected_systems"], [])
        self.assertEqual(result["statistical_findings"], [])

    def test_respiratory_mapping_and_custom_marker(self):
        rows = history(range(12, 19), context="inflight_vitals_check", source=_SOYUZ,
                       unit="breaths/min", kind="respiratory_rate_breaths_per_min")
        request = check_in(activity_context="inflight_vitals_check")
        request["indicators"]["respiratory_rate"]["value"] = "30"
        index = HistoryIndex(rows)
        result = assess_check_in(request, index)
        self.assertEqual(result["affected_systems"], ["respiratory"])
        self.assertEqual(result["body_marker"], "lungs")
        custom = DetectionConfig(body_markers={"respiratory": "respiratory_panel"})
        self.assertEqual(assess_check_in(request, index, config=custom)["body_marker"], "respiratory_panel")

    def test_sleep_and_mood_are_preserved_without_fabricated_baselines(self):
        result = assess_check_in(check_in(), HistoryIndex(history(range(69, 76))))
        self.assertEqual(result["overall_status"], "normal")
        sleep = indicator(result, "sleep_duration")
        mood = indicator(result, "mood")
        self.assertEqual(sleep["value"], "7.5")
        self.assertEqual(mood["category"], "good")
        self.assertIsNone(mood["value"])
        for evidence in (sleep, mood):
            self.assertIsNone(evidence["baseline"])
            self.assertEqual(evidence["statistics"]["status"], "insufficient_data")
        self.assertIn("categorical mood", " ".join(result["insufficient_data"]))

    def test_output_contract_decimal_serialization_and_offline_operation(self):
        rows = history(range(69, 76))
        request = check_in()
        precise = "72.0000000000000000000000000000001"
        request["indicators"]["heart_rate"]["value"] = precise
        blocked = OSError("network disabled")
        with patch.object(socket, "getaddrinfo", side_effect=blocked), patch.object(
            socket.socket, "connect", side_effect=blocked
        ), localcontext() as context:
            context.prec = 6
            result = assess_check_in(request, HistoryIndex(rows))
        self.assertEqual(result["data_origin"], "user")
        self.assertEqual(indicator(result)["statistics"]["history_origins"], ["synthetic"])
        self.assertEqual(indicator(result)["value"], precise)
        self.assertEqual(Decimal(indicator(result)["statistics"]["absolute_deviation"]), Decimal("1e-31"))
        self.assertEqual(validate_assessment(json.loads(json.dumps(result, allow_nan=False))), result)
        original = Path(_EXAMPLE).with_name("mock_assessment.json")
        self.assertEqual(validate_assessment(json.loads(original.read_text(encoding="utf-8")))["evidence"][0],
                         {"indicator": "heart_rate", "value": "72", "unit": "bpm", "baseline": None})
        result["evidence"][0]["statistics"]["anomaly"] = 0
        with self.assertRaisesRegex(ValueError, "statistics.anomaly"):
            validate_assessment(result)

    def test_extreme_finite_value_keeps_valid_output(self):
        request = check_in()
        request["indicators"]["heart_rate"]["value"] = "1e1000000"
        result = assess_check_in(request, HistoryIndex(history(range(69, 76))))
        evidence = indicator(result)
        self.assertEqual(evidence["value"], "1E+1000000")
        self.assertIsNone(evidence["statistics"]["anomaly"])
        self.assertIn("arithmetic range", " ".join(result["insufficient_data"]))
