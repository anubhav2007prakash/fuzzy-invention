"""Tests for cross-method explanation agreement (EXP-H core)."""
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

from backend.app.ml.data.synthetic import generate_flow_dataset
from backend.app.xai.agreement import agreement_matrix, compute_importances


class _Probe:
    def __init__(self, model):
        self.raw_model = model
        self.model_type = "random_forest"
        self.classes_ = model.classes_

    def predict(self, X):
        return self.raw_model.predict(X)

    def predict_proba(self, X):
        return self.raw_model.predict_proba(X)


def _fitted(seed=42, n=600):
    df = generate_flow_dataset(n_samples=n, random_state=seed)
    features = [c for c in df.columns if c != "label"]
    X, y = df[features].values, df["label"].values
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25,
                                              random_state=seed, stratify=y)
    model = RandomForestClassifier(n_estimators=30, max_depth=6, random_state=seed)
    model.fit(X_tr, y_tr)
    return _Probe(model), X_te, y_te, features


def test_all_three_methods_computed():
    detector, X_te, y_te, features = _fitted()
    methods = compute_importances(detector, X_te, y_te, features)
    assert set(methods) == {"shap", "permutation", "builtin"}
    for name, values in methods.items():
        assert set(values) == set(features)
        assert all(np.isfinite(v) for v in values.values())


def test_matrix_pairwise_and_consensus():
    detector, X_te, y_te, features = _fitted()
    methods = compute_importances(detector, X_te, y_te, features)
    matrix = agreement_matrix(methods, top_k=5)

    assert len(matrix["pairs"]) == 3  # 3 methods -> 3 pairs
    for pair in matrix["pairs"]:
        assert 0.0 <= pair["topk_overlap"] <= 1.0
        assert -1.0 <= pair["spearman"] <= 1.0
    assert 0.0 <= matrix["mean_topk_overlap"] <= 1.0
    assert len(matrix["consensus_ranking"]) == len(features)
    assert matrix["consensus_ranking"][0]  # a feature leads the consensus


def test_identical_rankings_give_perfect_agreement():
    shared = {"f1": 0.9, "f2": 0.7, "f3": 0.5, "f4": 0.3}
    matrix = agreement_matrix({"a": dict(shared), "b": dict(shared)}, top_k=4)
    assert matrix["mean_topk_overlap"] == 1.0
    assert all(p["spearman"] == 1.0 for p in matrix["pairs"])


def test_disjoint_rankings_give_zero_overlap():
    a = {"f1": 0.9, "f2": 0.7, "f3": 0.5, "f4": 0.3}
    b = {"f1": 0.3, "f2": 0.5, "f3": 0.7, "f4": 0.9}
    matrix = agreement_matrix({"a": a, "b": b}, top_k=2)
    assert matrix["pairs"][0]["overlap_count"] == 0
    assert matrix["pairs"][0]["topk_overlap"] == 0.0
    assert matrix["pairs"][0]["spearman"] < 0


def test_feature_rows_track_topk_membership():
    detector, X_te, y_te, features = _fitted()
    methods = compute_importances(detector, X_te, y_te, features)
    matrix = agreement_matrix(methods, top_k=5)
    top_consensus = matrix["consensus_ranking"][:5]
    rows = {r["feature"]: r for r in matrix["features"]}
    # consensus leaders should sit in multiple methods' top-k
    assert rows[top_consensus[0]]["methods_in_top_k"] >= 1
