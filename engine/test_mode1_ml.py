import importlib.util
import json
import socket
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from engine.mode1_detection import HistoryIndex, assess_check_in, assess_observation
from engine.mode1_ingestion import EvaluationLabel, Reading
from engine.mode1_ml import (
    assess_check_in_with_ml, assess_with_ml, extract_features, fit_models, load_models, save_models,
    score_observation,
)
from engine.mode1_ml_evaluation import chronological_split, evaluate
from engine.test_mode1_detection import _SKYLAB, _SOYUZ, check_in, observation

_VITALS = "inflight_vitals_check"


def vitals(day, mean=70, peak=95, rate=14, **changes):
    base = observation(day, mean, context=_VITALS, source=_SOYUZ)
    return replace(base, readings=(
        base.readings[0],
        Reading("heart_rate_peak_bpm", "bpm", Decimal(peak), "valid", str(peak)),
        Reading("respiratory_rate_breaths_per_min", "breaths/min", Decimal(rate), "valid", str(rate)),
    ), **changes)


class FeatureTests(unittest.TestCase):
    def test_feature_allowlist_ignores_provenance_and_source_context(self):
        row = vitals(2)
        self.assertEqual(extract_features(row), (70.0, 95.0, 14.0))
        changed = replace(row, source_context="high_workload_check", astronaut_id="someone_else",
                          source_row=777, mission_day=999, readings=tuple(reversed(row.readings)))
        self.assertEqual(extract_features(changed), extract_features(row))
        self.assertIsNone(extract_features(replace(row, activity_context="recovery")))
        self.assertIsNone(extract_features(replace(row, source_file=_SKYLAB)))

    def test_missing_invalid_incompatible_and_duplicate_features(self):
        row = vitals(2)
        for bad in (replace(row.readings[0], value=None, value_status="missing"),
                    replace(row.readings[0], value=Decimal("NaN")),
                    replace(row.readings[0], unit="L/min")):
            with self.subTest(bad=bad):
                self.assertIsNone(extract_features(replace(row, readings=(bad, *row.readings[1:]))))
        self.assertIsNone(extract_features(replace(row, readings=row.readings[:-1])))
        self.assertIsNone(extract_features(replace(row, readings=(*row.readings, row.readings[0]))))

    def test_chronological_split_disallows_overlap_and_duplicate_identity(self):
        earlier, later = vitals(4), vitals(5)
        self.assertEqual(chronological_split([later, earlier], cutoff=later.timestamp), ([earlier], [later]))
        with self.assertRaisesRegex(ValueError, "Duplicate observation"):
            chronological_split([earlier, replace(later, source_row=earlier.source_row)], cutoff=later.timestamp)
        with self.assertRaisesRegex(ValueError, "Duplicate observation"):
            chronological_split([earlier, replace(earlier, source_row=777)], cutoff=later.timestamp)

    def test_m2_fallback_needs_no_ml_dependency_or_model(self):
        row = vitals(9)
        history = HistoryIndex(vitals(day) for day in range(8))
        expected = assess_observation(row, history)
        with patch.dict("sys.modules", {"sklearn": None, "skops": None}):
            result = assess_with_ml(row, history)
        self.assertEqual(result["assessment"], expected)
        self.assertEqual(result["assessment"]["overall_status"], "insufficient_data")
        self.assertFalse(result["ml_finding"]["model_available"])
        self.assertIsNone(result["ml_finding"]["is_anomaly"])
        self.assertEqual(json.loads(json.dumps(result, allow_nan=False)), result)

    def test_manual_check_in_returns_primary_m2_and_unavailable_ml(self):
        payload = check_in(activity_context=_VITALS)
        history = HistoryIndex(vitals(day, mean=67 + day) for day in range(10))
        expected = assess_check_in(payload, history)
        with patch.dict("sys.modules", {"sklearn": None, "skops": None}):
            result = assess_check_in_with_ml(payload, history)
        self.assertEqual(expected["overall_status"], "normal")
        self.assertEqual(result["assessment"], expected)
        self.assertIsNone(result["assessment"]["optional_ml_findings"])
        finding = result["ml_finding"]
        self.assertFalse(finding["model_available"])
        self.assertIsNone(finding["anomaly_score"])
        self.assertIsNone(finding["is_anomaly"])


@unittest.skipUnless(importlib.util.find_spec("sklearn"), "optional scikit-learn is unavailable")
class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = [vitals(day, 66 + day % 9, 89 + day % 7, 12 + day % 5) for day in range(55)]
        cls.cutoff = vitals(55).timestamp
        cls.models = fit_models(cls.train, cutoff=cls.cutoff, dataset_version="fixture")

    def test_reproducible_fit_and_training_only_scaling(self):
        key, = self.models.models
        scaler = self.models.models[key]["pipeline"].named_steps["standardscaler"]
        features = [extract_features(row) for row in self.train]
        self.assertEqual(tuple(scaler.mean_), tuple(sum(field) / len(features) for field in zip(*features)))
        self.assertEqual(scaler.n_samples_seen_, 55)
        repeat = fit_models(reversed(self.train), cutoff=self.cutoff, dataset_version="fixture")
        row = vitals(56, 68, 92, 14)
        self.assertEqual(score_observation(row, self.models), score_observation(row, repeat))

    def test_outlier_and_unavailable_inference(self):
        typical = score_observation(vitals(56, 70, 92, 14), self.models)
        outlier = score_observation(vitals(56, 160, 195, 42), self.models)
        self.assertFalse(typical["is_anomaly"])
        self.assertTrue(outlier["is_anomaly"])
        self.assertGreater(outlier["anomaly_score"], typical["anomaly_score"])
        self.assertIsNone(score_observation(vitals(1), self.models)["is_anomaly"])
        self.assertIsNone(score_observation(vitals(56, astronaut_id="other"), self.models)["is_anomaly"])
        self.assertIsNone(score_observation(replace(vitals(56), readings=()), self.models)["is_anomaly"])

    def test_fitting_rejects_future_rows_and_does_not_pool_small_groups(self):
        with self.assertRaisesRegex(ValueError, "cutoff"):
            fit_models([*self.train, vitals(55)], cutoff=self.cutoff, dataset_version="fixture")
        other = [vitals(day, astronaut_id="other", source_row=day + 100) for day in range(30)]
        models = fit_models([*self.train[:30], *other], cutoff=self.cutoff, dataset_version="fixture")
        self.assertEqual(sorted(models.training_counts.values()), [30, 30])
        self.assertFalse(models.models)

    def test_labels_select_training_normals_and_holdout_labels_do_not_affect_fit(self):
        held_out = [vitals(55, 160, 180, 30), vitals(56), observation(57, 90)]
        labels = [
            EvaluationLabel(row.source_file, row.source_row, "mild" if index < 2 else "normal",
                            "synthetic_test", "high_workload_check")
            for index, row in enumerate([*self.train, *held_out])
        ]
        changing = [*labels[:-3], replace(labels[-3], expected_scenario_severity="critical"), *labels[-2:]]
        first, report = evaluate([*self.train, *held_out], labels, cutoff=self.cutoff)
        second, _ = evaluate([*self.train, *held_out], changing, cutoff=self.cutoff)
        self.assertEqual(report["fitted_training_rows"], 53)
        self.assertEqual(report["scored"], 2)
        self.assertEqual(report["held_out"], 3)
        self.assertEqual(report["unscored_labels"], {"normal": 1})
        self.assertEqual(report["full_holdout_metrics"]["m2"]["abstentions"], 1)
        self.assertEqual(report["full_holdout_metrics"]["ml"]["abstentions"], 1)
        self.assertEqual(report["full_holdout_metrics"]["hybrid"]["abstentions"], 1)
        for row in held_out:
            self.assertEqual(score_observation(row, first), score_observation(row, second))

    @unittest.skipUnless(importlib.util.find_spec("skops"), "optional skops is unavailable")
    def test_safe_persistence_and_offline_inference(self):
        blocked = OSError("network disabled")
        with tempfile.TemporaryDirectory() as directory, patch.object(
            socket, "getaddrinfo", side_effect=blocked
        ), patch.object(socket.socket, "connect", side_effect=blocked):
            path = Path(directory) / "model.skops"
            digest = save_models(self.models, path)
            loaded = load_models(path, expected_sha256=digest)
            row = vitals(56, 160, 195, 42)
            self.assertEqual(score_observation(row, loaded), score_observation(row, self.models))
            self.assertEqual(loaded.training_counts, self.models.training_counts)
            path.write_bytes(path.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "trusted SHA-256"):
                load_models(path, expected_sha256=digest)
