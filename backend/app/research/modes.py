"""Application modes (item: Research Mode vs Demo Mode).

Research Mode — everything: configurations, statistics, raw metrics,
    provenance, artifacts, reproducibility.
Demo Mode     — only the golden path: dataset -> prediction -> explanation
    -> evidence -> verification.

Mode is module-level state (single owner), defaults to research, switchable at
runtime; Demo Mode also flips the API into read-only for a public research demo
(no uploads, no training, no experiment runs — see the API guard).
"""
from __future__ import annotations

from typing import Any, Dict, List

MODES = ("research", "demo")

RESEARCH_SCOPE: List[str] = [
    "dashboard", "datasets", "models", "predictions", "explainability",
    "audit", "experiments", "professor-mode", "benchmark", "challenges",
    "provenance", "review", "docs", "settings",
]

DEMO_SCOPE: List[str] = [
    "datasets", "predictions", "explainability", "audit",
]

# Demo Mode golden path — the only mutating endpoints a visitor may reach.
# Everything else (uploads, training, experiment runs, reviews) is default-deny.
DEMO_ALLOWED_MUTATIONS = (
    "/predictions",      # run the model on a provided sample
    "/explanations",     # view the explanation
    "/audit/verify",     # verify the ledger
    "/audit/export",     # export evidence
    "/mode",             # escape hatch: switch back to Research Mode
)

_current_mode = "research"


def get_mode() -> str:
    return _current_mode


def set_mode(mode: str) -> str:
    global _current_mode
    normalized = (mode or "").strip().lower()
    if normalized not in MODES:
        raise ValueError(
            f"Unknown mode '{mode}'. Supported: {', '.join(MODES)}."
        )
    _current_mode = normalized
    return _current_mode


def mode_state() -> Dict[str, Any]:
    """Full mode descriptor consumed by the frontend shell."""
    is_demo = _current_mode == "demo"
    return {
        "mode": _current_mode,
        "read_only": is_demo,
        "scope": DEMO_SCOPE if is_demo else RESEARCH_SCOPE,
        "description": (
            "Demo Mode: golden-path read-only walkthrough "
            "(dataset → prediction → explanation → evidence → verification)."
            if is_demo else
            "Research Mode: full configurations, statistics, provenance, and "
            "reproducibility artifacts."
        ),
        "modes": list(MODES),
    }


def endpoint_allowed(method: str, path: str) -> bool:
    """Demo Mode default-denies mutations except the golden path (demo safety).

    Matching is suffix/segment based so `/mode` can never smuggle-match
    `/models/train`.
    """
    if _current_mode != "demo":
        return True
    method = method.upper()
    if method in ("GET", "HEAD", "OPTIONS"):
        return True
    normalized = path.rstrip("/").lower()
    if method != "POST":
        return False
    # exact-suffix routes
    if normalized.endswith("/predictions"):
        return True
    if normalized.endswith("/audit/verify"):
        return True
    if normalized.endswith("/mode"):
        return True
    if normalized.endswith("/explanations"):
        return True
    # parametrized route: POST /explanations/{prediction_id}
    if "/explanations/" in normalized:
        return True
    return False
