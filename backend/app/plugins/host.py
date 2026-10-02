"""PluginHost — the only application path that runs plugin code.

Plugins cannot:
- replace core hashing / ledger / notary (those kinds are rejected at register)
- skip dataset validation (generators are registered through DatasetService)
- skip experiment tracking (results are enriched by ExperimentService)
- skip evidence hashes (envelope keys from plugins are stripped, then reattached)
- persist explanations (ExplanationService remains the writer)
- replace core classification metrics
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional, Type

import pandas as pd

from backend.app.cryptography.hashing import sha256_hash
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.ml.evaluation.research_metrics import classification_metrics
from backend.app.ml.models.base import BaseDetector
from backend.app.plugins.registry import get_registry

CORE_METRIC_NAME = "classification"


class PluginHost:
    """Policy boundary between untrusted plugin factories and core workflows."""

    def __init__(self, registry=None):
        self.registry = registry or get_registry()

    def catalog(self, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.registry.list(kind)

    def create_model(
        self,
        name: str,
        hyperparameters: Optional[Dict[str, Any]] = None,
        random_seed: int = 42,
    ) -> BaseDetector:
        from backend.app.ml.registry import ModelRegistry

        detector = ModelRegistry.create_model(
            model_type=name,
            hyperparameters=hyperparameters,
            random_seed=random_seed,
        )
        if not isinstance(detector, BaseDetector):
            raise TypeError(
                f"Model plugin '{name}' must return a BaseDetector; "
                "TrainingService will not accept other objects."
            )
        return detector

    def ingest_dataset(
        self,
        db: Any,
        name: str = "synthetic_flows",
        dataset_name: Optional[str] = None,
        source: str = "plugin",
        **factory_kwargs: Any,
    ):
        """Run a dataset generator, then DatasetService validation + lineage."""
        from backend.app.services.dataset_service import DatasetService

        frame = self.registry.create("dataset", name, **factory_kwargs)
        if not isinstance(frame, pd.DataFrame):
            raise TypeError(
                f"Dataset plugin '{name}' must return a pandas DataFrame."
            )
        buffer = io.BytesIO()
        frame.to_csv(buffer, index=False)
        file_name = f"{name}.csv"
        return DatasetService(db).upload_and_register(
            file_content=buffer.getvalue(),
            file_name=file_name,
            dataset_name=dataset_name or name,
            source=source,
        )

    def create_explainer(self, name: str, *args: Any, **kwargs: Any) -> Any:
        explainer = self.registry.create("xai", name, *args, **kwargs)
        if not hasattr(explainer, "explain"):
            raise TypeError(
                f"XAI plugin '{name}' must provide an explain() method. "
                "Persistence is performed only by ExplanationService."
            )
        return explainer

    def compute_metrics(
        self,
        y_true: Any,
        y_pred: Any,
        y_prob: Any = None,
        supplementary: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Core metrics always come from research_metrics, never from a plugin."""
        core = classification_metrics(y_true, y_pred, y_prob)
        extra: Dict[str, Any] = {}
        for metric_name in supplementary or []:
            key = str(metric_name).strip().lower()
            if key == CORE_METRIC_NAME:
                raise ValueError(
                    "The core 'classification' metric cannot be invoked as a "
                    "supplementary plugin; it is already applied by the host."
                )
            produced = self.registry.create("metric", key)(y_true, y_pred, y_prob)
            extra[key] = produced
        return {"core": core, "supplementary": extra}

    def run_experiment(
        self,
        experiment_service: Any,
        name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a plugin experiment and attach the research envelope."""
        info = self.registry.require("experiment", name)
        normalized_id = str(
            info.metadata.get("experiment_id") or name
        ).upper().strip()
        cfg = experiment_service.validate_experiment_config(
            normalized_id, config or {}
        )
        raw = info.factory(**cfg)
        if not isinstance(raw, dict):
            raise TypeError(
                f"Experiment plugin '{name}' must return a dict result."
            )
        from backend.app.services.experiment_service import RESEARCH_ENVELOPE_KEYS

        raw = {key: value for key, value in raw.items() if key not in RESEARCH_ENVELOPE_KEYS}
        raw.setdefault("experiment_id", normalized_id)
        raw.setdefault("title", info.description or normalized_id)
        raw.setdefault("status", "COMPLETED")
        raw.setdefault("parameters", cfg)
        raw["plugins"] = [
            {
                "kind": info.kind,
                "name": info.name,
                "source": info.source,
                "core": info.core,
            }
        ]
        enriched = experiment_service.enrich_research_result(raw, cfg)
        filename = plugin_result_filename(normalized_id)
        out_file = experiment_service_results_dir() / filename
        import json

        with open(out_file, "w", encoding="utf-8") as handle:
            json.dump(enriched, handle, indent=2)
        return enriched

    def render_report(self, name: str, payload: Dict[str, Any]) -> Any:
        if not isinstance(payload, dict):
            raise TypeError("Report plugins format dict payloads only.")
        rendered = self.registry.create("report", name, payload)
        if name == "json":
            return payload
        text = rendered if isinstance(rendered, str) else str(rendered)
        return _append_evidence_fields(text, payload)


def plugin_result_filename(exp_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in exp_id.lower())
    return f"exp_plugin_{safe}.json"


def experiment_service_results_dir():
    from backend.app.services.experiment_service import RESULTS_DIR

    return RESULTS_DIR


def resolve_model_class(model_type: str) -> Optional[Type[BaseDetector]]:
    info = get_registry().get("model", model_type)
    if info is None:
        return None
    factory = info.factory
    if isinstance(factory, type) and issubclass(factory, BaseDetector):
        return factory
    return None


def _append_evidence_fields(text: str, payload: Dict[str, Any]) -> str:
    """Guarantee evidence hashes survive report formatting."""
    extra_lines = []
    for key in ("result_hash", "configuration_hash"):
        value = payload.get(key)
        if value and str(value) not in text:
            extra_lines.append(f"{key}: {value}")
    if not extra_lines:
        return text
    suffix = "\n".join(extra_lines)
    if text.endswith("\n"):
        return text + suffix + "\n"
    return text + "\n" + suffix + "\n"


def payload_digest(payload: Dict[str, Any]) -> str:
    """Host-owned digest helper — plugins must not supply their own evidence hash."""
    return sha256_hash(canonicalize(payload))
