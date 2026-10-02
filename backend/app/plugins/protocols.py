"""In-process plugin contracts.

Plugins are Python callables loaded into the same process as SentinelCrypt.
They are not services.  Cryptographic evidence, hashing, canonicalization,
the hash chain, Merkle trees, and notarization are **not** plugin kinds —
those stay in `backend.app.cryptography` (trusted computing base).

A plugin may only supply a research component.  The host in `host.py` is
what trains models, registers datasets, tracks experiments, and emits
evidence.  Direct factory calls are not an application workflow.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Protocol, runtime_checkable

import numpy as np
import pandas as pd

from backend.app.ml.models.base import BaseDetector

# Kinds the registry accepts.  Crypto is intentionally absent.
PLUGIN_KINDS = ("model", "dataset", "xai", "metric", "experiment", "report")

# Kinds that must never be replaced once registered as core.
CORE_PROTECTED_KINDS = PLUGIN_KINDS


@runtime_checkable
class ModelPlugin(Protocol):
    """Must be a BaseDetector subclass used only through TrainingService."""

    model_type: str

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str] | None = None,
    ) -> BaseDetector: ...

    def predict(self, X: np.ndarray) -> np.ndarray: ...

    def predict_proba(self, X: np.ndarray) -> np.ndarray: ...


@runtime_checkable
class DatasetPlugin(Protocol):
    """Returns a labelled DataFrame.  The host registers it via DatasetService."""

    def __call__(self, *args: Any, **kwargs: Any) -> pd.DataFrame: ...


@runtime_checkable
class ExplainerPlugin(Protocol):
    """Produces attributions.  Persistence goes through ExplanationService."""

    def explain(self, X: np.ndarray) -> Any: ...


@runtime_checkable
class MetricPlugin(Protocol):
    """Supplementary metric.  Cannot replace core classification_metrics."""

    def __call__(
        self,
        y_true: Any,
        y_pred: Any,
        y_prob: Any = None,
    ) -> Mapping[str, float]: ...


@runtime_checkable
class ExperimentPlugin(Protocol):
    """Returns a result dict without a research envelope.

    PluginHost strips envelope keys and ExperimentService.enrich_research_result
    attaches hashes, the run manifest, and the trust profile.
    """

    def __call__(self, **config: Any) -> Dict[str, Any]: ...


@runtime_checkable
class ReportPlugin(Protocol):
    """Formats an already-computed payload.  Must not invent metrics."""

    def __call__(self, payload: Dict[str, Any]) -> str: ...
