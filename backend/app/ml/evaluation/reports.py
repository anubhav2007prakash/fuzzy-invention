"""Evaluation Report Generators for SentinelCrypt AI."""
from __future__ import annotations

import json
from typing import Any, Dict
from backend.app.ml.evaluation.evaluator import EvaluationResult


def generate_markdown_report(result: EvaluationResult, model_name: str = "Model") -> str:
    """Generate a GitHub Flavored Markdown summary report for evaluation results."""
    m = result.metrics

    def _fmt(val: Any) -> str:
        if val is None:
            return "N/A"
        try:
            return f"{float(val):.4f}"
        except (ValueError, TypeError):
            return str(val)

    lines = [
        f"### Evaluation Report: {model_name}",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Accuracy | {_fmt(m.get('accuracy'))} |",
        f"| Precision (Macro) | {_fmt(m.get('precision_macro'))} |",
        f"| Recall (Macro) | {_fmt(m.get('recall_macro'))} |",
        f"| F1-Score (Macro) | {_fmt(m.get('f1_macro'))} |",
        f"| F1-Score (Weighted) | {_fmt(m.get('f1_weighted'))} |",
        f"| ROC-AUC | {_fmt(m.get('roc_auc'))} |",
        f"| PR-AUC | {_fmt(m.get('pr_auc'))} |",
        f"| Brier Score | {_fmt(m.get('brier_score'))} |",
        f"| Latency (ms/sample) | {result.latency_ms_per_sample:.4f} ms |",
        f"| Total Samples | {result.total_samples} |",
        "",
        "#### Confusion Matrix",
        "```json",
        json.dumps(result.confusion_matrix, indent=2),
        "```",
    ]
    return "\n".join(lines)
