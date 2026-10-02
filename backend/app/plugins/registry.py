"""Plugin registry — catalog of in-process research extensions.

Core code asks the registry for *names*; PluginHost is the only supported
invocation path for application workflows.  Third-party extensions drop a
``.py`` file into ``plugins/`` at the repo root and register on import.

Plugins cannot register cryptographic evidence methods and cannot replace
core (builtin) entries.
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.app.core.logging import get_logger
from backend.app.plugins.protocols import PLUGIN_KINDS

logger = get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = _REPO_ROOT / "plugins"

FORBIDDEN_KINDS = ("crypto", "cryptography", "hash", "notary", "evidence")


@dataclass
class PluginInfo:
    kind: str
    name: str
    factory: Callable[..., Any]
    description: str = ""
    source: str = "builtin"
    core: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "core": self.core,
            "metadata": self.metadata,
        }


class PluginRegistry:
    """Kind -> name -> PluginInfo.  Single owner of plugin metadata."""

    def __init__(self) -> None:
        self._plugins: Dict[str, Dict[str, PluginInfo]] = {k: {} for k in PLUGIN_KINDS}

    def register(
        self,
        kind: str,
        name: str,
        factory: Callable[..., Any],
        description: str = "",
        source: str = "builtin",
        metadata: Optional[Dict[str, Any]] = None,
        replace: bool = False,
        core: bool = False,
    ) -> PluginInfo:
        kind_key = str(kind).strip().lower()
        if kind_key in FORBIDDEN_KINDS:
            raise ValueError(
                f"Plugin kind '{kind}' is not allowed. Cryptographic evidence "
                "methods are core TCB and cannot be registered as plugins."
            )
        if kind_key not in self._plugins:
            raise ValueError(
                f"Unknown plugin kind '{kind}'. Supported: {', '.join(PLUGIN_KINDS)}."
            )
        if not name or not str(name).strip():
            raise ValueError("Plugin name must be a non-empty string.")
        if not callable(factory):
            raise ValueError(f"Plugin '{name}' factory must be callable.")
        name = str(name).strip().lower()
        existing = self._plugins[kind_key].get(name)
        if existing is not None:
            if existing.core:
                raise ValueError(
                    f"Cannot replace core plugin '{kind_key}:{name}'."
                )
            if not replace:
                raise ValueError(f"Plugin '{kind_key}:{name}' is already registered.")
        info = PluginInfo(
            kind=kind_key,
            name=name,
            factory=factory,
            description=description,
            source=source,
            core=bool(core),
            metadata=metadata or {},
        )
        self._plugins[kind_key][name] = info
        return info

    def get(self, kind: str, name: str) -> Optional[PluginInfo]:
        return self._plugins.get(kind, {}).get(str(name).strip().lower())

    def create(self, kind: str, name: str, *args: Any, **kwargs: Any) -> Any:
        """Instantiate a factory.  Application workflows should use PluginHost."""
        info = self.require(kind, name)
        return info.factory(*args, **kwargs)

    def require(self, kind: str, name: str) -> PluginInfo:
        info = self.get(kind, name)
        if info is None:
            available = ", ".join(sorted(self._plugins.get(kind, {}))) or "none"
            raise ValueError(
                f"No {kind} plugin named '{name}'. Registered: {available}."
            )
        return info

    def list(self, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        kinds = [kind] if kind else list(PLUGIN_KINDS)
        out: List[Dict[str, Any]] = []
        for k in kinds:
            if k not in self._plugins:
                raise ValueError(f"Unknown plugin kind '{k}'.")
            out.extend(self._plugins[k][name].to_dict() for name in sorted(self._plugins[k]))
        return out

    def counts(self) -> Dict[str, int]:
        return {k: len(v) for k, v in self._plugins.items()}

    def unregister(self, kind: str, name: str) -> None:
        info = self.get(kind, name)
        if info is None:
            return
        if info.core:
            raise ValueError(f"Cannot unregister core plugin '{kind}:{name}'.")
        del self._plugins[kind][str(name).strip().lower()]


_registry = PluginRegistry()
_builtins_registered = False
_discovered = False


def get_registry() -> PluginRegistry:
    """Module-level registry singleton (builtins + reference plugins on first access)."""
    global _builtins_registered, _discovered
    if not _builtins_registered:
        _builtins_registered = True
        register_builtin_plugins(_registry)
    if not _discovered:
        _discovered = True
        discover_plugins(_registry)
    return _registry


def register_builtin_plugins(registry: PluginRegistry) -> None:
    """Map existing core capabilities onto the plugin catalog (idempotent)."""
    from backend.app.ml.data.synthetic import generate_flow_dataset
    from backend.app.ml.evaluation.research_metrics import classification_metrics
    from backend.app.ml.models.logistic_regression import LogisticRegressionDetector
    from backend.app.ml.models.random_forest import RandomForestDetector
    from backend.app.ml.evaluation.reports import generate_markdown_report
    from backend.app.xai.shap_explainer import SHAPExplainer
    from backend.app.xai.stability import ExplanationStabilityAnalyzer

    registry.register(
        "model",
        "logistic_regression",
        LogisticRegressionDetector,
        description="Core detector: Logistic Regression.",
        core=True,
        replace=True,
    )
    registry.register(
        "model",
        "random_forest",
        RandomForestDetector,
        description="Core detector: Random Forest.",
        core=True,
        replace=True,
    )
    registry.register(
        "dataset",
        "synthetic_flows",
        generate_flow_dataset,
        description="Deterministic synthetic network-flow generator (labelled synthetic).",
        metadata={"synthetic": True},
        core=True,
        replace=True,
    )
    registry.register(
        "xai",
        "shap",
        SHAPExplainer,
        description="SHAP Linear/Tree explainer wrapper.",
        core=True,
        replace=True,
    )
    registry.register(
        "xai",
        "stability",
        ExplanationStabilityAnalyzer,
        description="Perturbation-based explanation stability analyzer.",
        core=True,
        replace=True,
    )
    registry.register(
        "metric",
        "classification",
        classification_metrics,
        description="Core detection metric suite (F1/macro-F1/PR-AUC/ECE/Brier). Non-replaceable.",
        core=True,
        replace=True,
        metadata={"role": "core"},
    )
    registry.register(
        "report",
        "json",
        lambda payload: payload,
        description="JSON report passthrough (does not rewrite evidence fields).",
        core=True,
        replace=True,
    )
    registry.register(
        "report",
        "markdown",
        _core_markdown_report,
        description="Markdown formatter for evaluation/experiment payloads.",
        core=True,
        replace=True,
        metadata={"uses": "backend.app.ml.evaluation.reports"},
    )
    # Keep generate_markdown_report imported so the catalog is honest.
    _ = generate_markdown_report


def _core_markdown_report(payload: Dict[str, Any]) -> str:
    """Format a dict payload as markdown; evidence hashes are appended by the host."""
    from backend.app.ml.evaluation.reports import generate_markdown_report
    from backend.app.ml.evaluation.evaluator import EvaluationResult

    if isinstance(payload.get("evaluation"), EvaluationResult):
        return generate_markdown_report(
            payload["evaluation"],
            model_name=str(payload.get("model_name", "Model")),
        )
    title = payload.get("title") or payload.get("experiment_id") or "Report"
    lines = [f"# {title}", ""]
    metrics = payload.get("metrics")
    if isinstance(metrics, dict) and metrics:
        lines.extend(["| Metric | Value |", "|---|---|"])
        for key, value in metrics.items():
            lines.append(f"| {key} | {value} |")
        lines.append("")
    for key in ("result_hash", "configuration_hash", "status"):
        if key in payload:
            lines.append(f"- **{key}**: `{payload[key]}`")
    return "\n".join(lines).rstrip() + "\n"


def discover_plugins(
    registry: Optional[PluginRegistry] = None,
    directory: Optional[Path] = None,
) -> Dict[str, Any]:
    """Import every ``*.py`` in the plugin directory; modules register on import."""
    target = registry if registry is not None else get_registry()
    # When called with an explicit directory (tests), do not recurse into get_registry.
    directory = Path(directory or PLUGIN_DIR)
    loaded: List[str] = []
    errors: Dict[str, str] = {}
    skipped: List[str] = []
    if not directory.is_dir():
        return {
            "directory": str(directory),
            "exists": False,
            "loaded": loaded,
            "errors": errors,
            "skipped": skipped,
        }

    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            skipped.append(path.name)
            continue
        module_name = f"sentinel_plugin_{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load spec for {path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            loaded.append(path.name)
        except Exception as exc:
            logger.warning("Plugin %s failed to load: %s", path.name, exc)
            errors[path.name] = str(exc)
    return {
        "directory": str(directory),
        "exists": True,
        "loaded": loaded,
        "errors": errors,
        "skipped": skipped,
        "counts": target.counts(),
    }
