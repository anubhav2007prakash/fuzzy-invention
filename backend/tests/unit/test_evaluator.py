"""Unit tests for the Model Evaluator, metrics, and reporting harness."""
import unittest
import numpy as np

from backend.app.ml.evaluation.evaluator import EvaluationResult, ModelEvaluator
from backend.app.ml.evaluation.metrics import (
    compute_confusion_matrix_dict,
    compute_detailed_report,
    compute_metrics,
)
from backend.app.ml.evaluation.reports import generate_markdown_report
from backend.app.ml.models.logistic_regression import LogisticRegressionDetector


class TestEvaluator(unittest.TestCase):
    def setUp(self):
        self.y_true = np.array([0, 1, 0, 0, 1, 1, 0, 1, 0, 1])
        self.y_pred = np.array([0, 1, 0, 0, 0, 1, 0, 1, 1, 1])
        # Probabilities: n_samples x 2
        self.y_prob = np.array([
            [0.9, 0.1],
            [0.2, 0.8],
            [0.85, 0.15],
            [0.7, 0.3],
            [0.6, 0.4],  # False negative
            [0.1, 0.9],
            [0.8, 0.2],
            [0.3, 0.7],
            [0.4, 0.6],  # False positive
            [0.05, 0.95],
        ])
        self.label_names = ["BENIGN", "ATTACK"]

    def test_compute_metrics_binary(self):
        m = compute_metrics(
            y_true=self.y_true,
            y_pred=self.y_pred,
            y_prob=self.y_prob,
            label_names=self.label_names,
        )
        self.assertIn("accuracy", m)
        self.assertIn("f1_macro", m)
        self.assertIn("f1_weighted", m)
        self.assertIn("precision_macro", m)
        self.assertIn("recall_macro", m)
        self.assertIn("roc_auc", m)
        self.assertIn("pr_auc", m)
        self.assertIn("brier_score", m)

        self.assertEqual(m["accuracy"], 0.8)
        self.assertAlmostEqual(m["precision"], m["precision_macro"])
        self.assertAlmostEqual(m["recall"], m["recall_macro"])
        self.assertAlmostEqual(m["f1"], m["f1_macro"])
        self.assertIsNotNone(m["roc_auc"])
        self.assertGreater(m["roc_auc"], 0.5)

    def test_compute_confusion_matrix_dict(self):
        cm = compute_confusion_matrix_dict(
            y_true=self.y_true,
            y_pred=self.y_pred,
            label_names=self.label_names,
        )
        self.assertIn("matrix", cm)
        self.assertIn("labels", cm)
        self.assertEqual(len(cm["labels"]), 2)
        self.assertEqual(cm["labels"], ["BENIGN", "ATTACK"])
        # Total counts should sum to 10
        total = sum(sum(row) for row in cm["matrix"])
        self.assertEqual(total, 10)

    def test_compute_detailed_report(self):
        rep = compute_detailed_report(
            y_true=self.y_true,
            y_pred=self.y_pred,
            label_names=self.label_names,
        )
        self.assertIn("macro avg", rep)
        self.assertIn("weighted avg", rep)
        self.assertIn("accuracy", rep)

    def test_model_evaluator_run(self):
        # Create a mock detector
        X = np.random.randn(20, 4)
        y = np.random.randint(0, 2, size=20)
        detector = LogisticRegressionDetector(random_seed=42)
        detector.fit(X, y)

        evaluator = ModelEvaluator()
        result = evaluator.evaluate(
            model=detector,
            X_test=X,
            y_test=y,
            label_names=["BENIGN", "MALICIOUS"],
        )

        self.assertIsInstance(result, EvaluationResult)
        self.assertEqual(result.total_samples, 20)
        self.assertGreater(result.latency_ms_per_sample, 0.0)
        self.assertIn("accuracy", result.metrics)
        self.assertIn("matrix", result.confusion_matrix)

        # Markdown report generation
        md = generate_markdown_report(result, model_name="TestLR")
        self.assertIn("Evaluation Report: TestLR", md)
        self.assertIn("Confusion Matrix", md)


if __name__ == "__main__":
    unittest.main()
