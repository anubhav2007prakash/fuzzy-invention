"""Evaluation package."""
from backend.app.ml.evaluation.evaluator import EvaluationResult, ModelEvaluator
from backend.app.ml.evaluation.metrics import (
    compute_confusion_matrix_dict,
    compute_detailed_report,
    compute_metrics,
)
from backend.app.ml.evaluation.reports import generate_markdown_report

__all__ = [
    "compute_metrics",
    "compute_confusion_matrix_dict",
    "compute_detailed_report",
    "EvaluationResult",
    "ModelEvaluator",
    "generate_markdown_report",
]
