"""XAI package — Explainable AI for SentinelCrypt AI.

Exports:
    SHAPExplainer          — wraps shap.LinearExplainer / TreeExplainer.
    FeatureContribution    — single-feature attribution dataclass.
    SHAPResult             — full explanation result for one sample.
    ExplanationStabilityAnalyzer — cosine-similarity-based stability scorer.
    StabilityReport        — output of stability analysis.
"""
from backend.app.xai.shap_explainer import (
    FeatureContribution,
    SHAPExplainer,
    SHAPResult,
)
from backend.app.xai.stability import (
    ExplanationStabilityAnalyzer,
    StabilityReport,
)

__all__ = [
    "FeatureContribution",
    "SHAPExplainer",
    "SHAPResult",
    "ExplanationStabilityAnalyzer",
    "StabilityReport",
]
