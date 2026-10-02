"""Cross-method explanation agreement (EXP-H).

Compares three importance methods on the same fitted model + holdout set:
  1. SHAP            — mean |attribution| over a sample of holdout rows
  2. permutation     — sklearn permutation_importance (f1 scoring)
  3. built-in        — feature_importances_ (RF) or |coef| (linear)

Outputs an agreement matrix (pairwise top-k overlap + Spearman rank correlation),
a per-feature rank table, and a Borda-count consensus ranking.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

import numpy as np
from sklearn.inspection import permutation_importance

from backend.app.core.logging import get_logger
from backend.app.xai.shap_explainer import SHAPExplainer

logger = get_logger(__name__)

try:
    from scipy import stats as _stats
except Exception:  # pragma: no cover
    _stats = None


def _shap_importance(detector, X, feature_names, max_samples: int = 50) -> Dict[str, float]:
    """Global SHAP importance = mean |SHAP| over up to max_samples rows."""
    n = min(len(X), max_samples)
    sample = X[:n]
    explainer = SHAPExplainer(
        detector=detector,
        X_background=X[: min(len(X), 100)],
        feature_names=list(feature_names),
    )
    totals = np.zeros(len(feature_names))
    for i in range(n):
        result = explainer.explain(sample[i:i + 1])
        totals += np.abs([c.shap_value for c in result.contributions])
    return {name: float(v) for name, v in zip(feature_names, totals / max(n, 1))}


def compute_importances(
    detector,
    X: np.ndarray,
    y: np.ndarray,
    feature_names: Sequence[str],
    seed: int = 42,
    n_repeats: int = 5,
) -> Dict[str, Dict[str, float]]:
    """Compute all three importance vectors keyed by method name."""
    feature_names = list(feature_names)
    methods: Dict[str, Dict[str, float]] = {}

    # 1. built-in
    raw = detector.raw_model
    if hasattr(raw, "feature_importances_"):
        builtin = dict(zip(feature_names, map(float, raw.feature_importances_)))
    elif hasattr(raw, "coef_"):
        coef = np.asarray(raw.coef_)
        builtin = dict(zip(feature_names, map(float, np.abs(coef).ravel()[: len(feature_names)])))
    else:
        builtin = {}
    if builtin:
        methods["builtin"] = builtin

    # 2. permutation
    try:
        perm = permutation_importance(
            raw, X, y, n_repeats=n_repeats, random_state=seed, scoring="f1"
        )
        methods["permutation"] = {
            name: float(v) for name, v in zip(feature_names, perm.importances_mean)
        }
    except Exception as exc:
        logger.warning("Permutation importance failed: %s", exc)

    # 3. SHAP
    try:
        methods["shap"] = _shap_importance(detector, X, feature_names)
    except Exception as exc:
        logger.warning("SHAP importance failed: %s", exc)

    return methods


def _rank(method: Dict[str, float]) -> List[str]:
    """Deterministic descending rank (value desc, name asc tie-break)."""
    return sorted(method.keys(), key=lambda k: (-method[k], k))


def _spearman(ra: List[str], rb: List[str]) -> float:
    pos_a = {name: i for i, name in enumerate(ra)}
    pos_b = {name: i for i, name in enumerate(rb)}
    names = sorted(set(ra) | set(rb))
    xa = [pos_a.get(n, len(names)) for n in names]
    xb = [pos_b.get(n, len(names)) for n in names]
    if _stats is not None:
        corr = _stats.spearmanr(xa, xb).correlation
        return round(float(corr), 4) if corr == corr else 0.0
    # fallback: Pearson on ranks
    xa, xb = np.asarray(xa, float), np.asarray(xb, float)
    if xa.std() == 0 or xb.std() == 0:
        return 0.0
    return round(float(np.corrcoef(xa, xb)[0, 1]), 4)


def agreement_matrix(
    methods: Dict[str, Dict[str, float]],
    top_k: int = 5,
) -> Dict[str, Any]:
    """Pairwise top-k overlap + Spearman correlation between every method pair."""
    ranks = {name: _rank(vals) for name, vals in methods.items()}
    names = sorted(ranks)
    pairs: List[Dict[str, Any]] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            k = min(top_k, len(ranks[a]), len(ranks[b]))
            overlap = sorted(set(ranks[a][:k]) & set(ranks[b][:k]))
            pairs.append({
                "method_a": a,
                "method_b": b,
                "top_k": k,
                "overlap_count": len(overlap),
                "overlap_features": overlap,
                "topk_overlap": round(len(overlap) / k, 4) if k else 0.0,
                "spearman": _spearman(ranks[a], ranks[b]),
            })

    # Per-feature rank table
    feature_rows: List[Dict[str, Any]] = []
    all_features = sorted({f for m in methods.values() for f in m})
    for feat in all_features:
        row: Dict[str, Any] = {"feature": feat}
        agreeing_topk = 0
        for m in names:
            rank_i = ranks[m].index(feat) + 1 if feat in ranks[m] else None
            row[f"rank_{m}"] = rank_i
            if rank_i is not None and rank_i <= top_k:
                agreeing_topk += 1
        row["methods_in_top_k"] = agreeing_topk
        row["all_agree"] = agreeing_topk == len(names)
        feature_rows.append(row)
    feature_rows.sort(key=lambda r: (-r["methods_in_top_k"], r["feature"]))

    # Borda consensus: sum of (n - rank) per method
    n_feats = len(all_features)
    borda: Dict[str, float] = {f: 0.0 for f in all_features}
    for m in names:
        for pos, feat in enumerate(ranks[m]):
            borda[feat] += (n_feats - pos)
    consensus = sorted(borda, key=lambda f: (-borda[f], f))

    pair_scores = [p["topk_overlap"] for p in pairs]
    return {
        "methods": names,
        "top_k": top_k,
        "pairs": pairs,
        "mean_topk_overlap": round(float(np.mean(pair_scores)), 4) if pair_scores else 0.0,
        "features": feature_rows,
        "consensus_ranking": consensus,
        "importances": methods,
        "ranks": ranks,
    }
