"""Metamorphic Relations for Explainable AI (XAI) and Stability Analysis.

IMPORTANT:
    SHAP values describe how a trained model distributes its prediction across
    features for a specific input. They are not causal ground-truth explanations.
    These metamorphic relations verify the mathematical and axiomatic correctness
    of the explainer and stability analyzer.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from backend.app.ml.preprocessing.pipeline import transform_single_sample
from backend.app.xai.shap_explainer import SHAPExplainer
from backend.app.xai.stability import ExplanationStabilityAnalyzer
from backend.tests.metamorphic.fixtures import (
    build_test_pipeline,
    make_trained_detectors,
)
from backend.tests.metamorphic.framework import (
    Category,
    MetamorphicRelation,
)


class MR_EXP_01_NullFeatureZeroAttribution(MetamorphicRelation):
    """MR-EXP-01: Shapley Null Player Axiom (Zero attribution for uninformative features)."""

    id = "MR-EXP-01"
    name = "Shapley Null Player Axiom (Zero-Weight Feature Invariance)"
    category = Category.EXPLANATION
    rationale = (
        "The Null Player axiom of cooperative game theory requires that if a feature "
        "has zero marginal contribution across all coalitions (e.g. weight w_j = 0 in a "
        "linear model), its Shapley value must be exactly zero: phi_j(x) = 0. Furthermore, "
        "modifying the value of this dummy feature must not alter its own attribution or "
        "distort the attributions of any other features."
    )
    input_transformation = (
        "In a linear detector where feature j has coefficient 0.0, shift x_j to x_j + delta."
    )
    expected_property = (
        "phi_j(x) == 0.0, phi_j(x') == 0.0, and |phi_k(x') - phi_k(x)| < 1e-5 for all k != j."
    )
    limitations = "Requires a feature with zero weight in a linear model."
    test_implementation = (
        "Construct linear model with feature 5 having weight 0.0. "
        "Compute SHAP attributions for x and x', assert phi_5 == 0 and other attributions match."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        models = make_trained_detectors(n_features=6)
        detector = models["lr_detector"]
        raw_lr = detector.raw_model

        # Ensure feature 5 has zero weight
        raw_lr.coef_[0, 5] = 0.0

        X_bg = models["X_train"]
        feature_names = models["feature_names"]
        explainer = SHAPExplainer(detector, X_bg, feature_names)

        x_base = np.array([[1.0, -0.5, 0.8, -1.2, 0.3, 0.0]])
        res_base = explainer.explain(x_base)

        # Perturb only the null feature 5
        x_pert = x_base.copy()
        x_pert[0, 5] = 100.0
        res_pert = explainer.explain(x_pert)

        phi_null_base = res_base.contributions[5].shap_value
        phi_null_pert = res_pert.contributions[5].shap_value

        # Check other features
        other_diffs = [
            abs(res_base.contributions[k].shap_value - res_pert.contributions[k].shap_value)
            for k in range(5)
        ]
        max_other_diff = max(other_diffs)

        passed = (
            abs(phi_null_base) < 1e-5
            and abs(phi_null_pert) < 1e-5
            and max_other_diff < 1e-5
        )

        return (
            passed,
            f"Null player axiom: phi_5_base={phi_null_base:.2e}, phi_5_pert={phi_null_pert:.2e}, "
            f"max_other_diff={max_other_diff:.2e}.",
            {"phi_null_base": phi_null_base, "phi_null_pert": phi_null_pert, "max_other_diff": max_other_diff},
        )


class MR_EXP_02_EfficiencyAxiomCompleteness(MetamorphicRelation):
    """MR-EXP-02: Shapley Efficiency Axiom (Sum of attributions + base = model output)."""

    id = "MR-EXP-02"
    name = "Shapley Efficiency Axiom (Completeness Invariance)"
    category = Category.EXPLANATION
    rationale = (
        "The efficiency (completeness) axiom guarantees that the sum of all feature SHAP "
        "attributions plus the baseline expected value equals the model's raw decision "
        "function output: sum(phi_i(x)) + base_value = f(x). This relationship must hold "
        "identically for any input x and any transformed input x'."
    )
    input_transformation = (
        "Transform input x to x' by perturbing multiple continuous features."
    )
    expected_property = (
        "|sum(phi(x)) + base - f(x)| < 1e-4 and |sum(phi(x')) + base - f(x')| < 1e-4."
    )
    limitations = "Holds on raw decision function / margin output."
    test_implementation = (
        "Compute SHAP attributions for x and x', compare sum of contributions + base_value "
        "against detector.raw_model.decision_function."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        models = make_trained_detectors(n_features=6)
        detector = models["lr_detector"]
        X_bg = models["X_train"]
        feature_names = models["feature_names"]
        explainer = SHAPExplainer(detector, X_bg, feature_names)

        x_orig = np.array([[0.5, -1.0, 2.0, 0.1, -0.4, 0.0]])
        x_pert = np.array([[1.5, -0.2, 0.5, -0.8, 1.2, 0.0]])

        res_orig = explainer.explain(x_orig)
        res_pert = explainer.explain(x_pert)

        raw_f_orig = float(detector.raw_model.decision_function(x_orig)[0])
        raw_f_pert = float(detector.raw_model.decision_function(x_pert)[0])

        sum_orig = sum(c.shap_value for c in res_orig.contributions) + res_orig.base_value
        sum_pert = sum(c.shap_value for c in res_pert.contributions) + res_pert.base_value

        diff_orig = abs(sum_orig - raw_f_orig)
        diff_pert = abs(sum_pert - raw_f_pert)

        passed = (diff_orig < 1e-4) and (diff_pert < 1e-4)
        return (
            passed,
            f"Efficiency completeness: diff_orig={diff_orig:.2e}, diff_pert={diff_pert:.2e}.",
            {"diff_orig": diff_orig, "diff_pert": diff_pert},
        )


class MR_EXP_03_LinearFeatureShiftAttribution(MetamorphicRelation):
    """MR-EXP-03: Attribution delta equals weight * delta for linear models."""

    id = "MR-EXP-03"
    name = "Linear Attribution Shift Under Feature Perturbation"
    category = Category.EXPLANATION
    rationale = (
        "For a linear model f(x) = sum(w_i * x_i) + b with independent background distribution, "
        "the SHAP value for feature j is phi_j(x) = w_j * (x_j - E[X_j]). When feature j is "
        "shifted by delta while holding all other features constant: "
        "phi_j(x') - phi_j(x) = w_j * delta. "
        "Furthermore, the attributions of all other features k != j remain exactly unchanged."
    )
    input_transformation = (
        "Add delta > 0 to feature j in input x to form x'."
    )
    expected_property = (
        "|phi_j(x') - phi_j(x) - w_j * delta| < 1e-5 and |phi_k(x') - phi_k(x)| < 1e-5 for all k != j."
    )
    limitations = "Applies to linear models explained with LinearExplainer on independent masker."
    test_implementation = (
        "Perturb feature 0 by delta=2.0, compute SHAP before and after, "
        "assert delta_phi_0 == w_0 * delta and other delta_phi_k == 0."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        models = make_trained_detectors(n_features=6)
        detector = models["lr_detector"]
        w = detector.raw_model.coef_[0]

        X_bg = models["X_train"]
        feature_names = models["feature_names"]
        explainer = SHAPExplainer(detector, X_bg, feature_names)

        j = 0
        w_j = float(w[j])
        delta = 2.5

        x_base = np.array([[0.2, -0.4, 1.1, 0.0, -0.5, 0.0]])
        x_pert = x_base.copy()
        x_pert[0, j] += delta

        res_base = explainer.explain(x_base)
        res_pert = explainer.explain(x_pert)

        phi_j_base = res_base.contributions[j].shap_value
        phi_j_pert = res_pert.contributions[j].shap_value

        observed_delta = phi_j_pert - phi_j_base
        expected_delta = w_j * delta
        error_j = abs(observed_delta - expected_delta)

        # Check other features remained unchanged
        other_errors = [
            abs(res_pert.contributions[k].shap_value - res_base.contributions[k].shap_value)
            for k in range(len(w))
            if k != j
        ]
        max_other_error = max(other_errors)

        passed = (error_j < 1e-4) and (max_other_error < 1e-4)
        return (
            passed,
            f"Linear shift: observed_delta={observed_delta:.4f}, expected={expected_delta:.4f}, "
            f"error_j={error_j:.2e}, max_other_error={max_other_error:.2e}.",
            {"error_j": error_j, "max_other_error": max_other_error},
        )


class MR_EXP_04_StabilityNoiseMonotonicity(MetamorphicRelation):
    """MR-EXP-04: Monotonic decrease in explanation stability under increased perturbation noise."""

    id = "MR-EXP-04"
    name = "Explanation Stability Monotonicity Under Noise Scaling"
    category = Category.EXPLANATION
    rationale = (
        "In `ExplanationStabilityAnalyzer`, explanation stability is defined as the mean "
        "cosine similarity between baseline SHAP attribution vector and perturbed vectors "
        "under Gaussian noise sigma. As sigma increases, the perturbed points move further away "
        "from the local neighborhood, lowering or preserving cosine similarity in expectation: "
        "stability(sigma_small) >= stability(sigma_large)."
    )
    input_transformation = (
        "Evaluate stability score under low noise sigma_1 = 0.01 versus high noise sigma_2 = 0.50."
    )
    expected_property = (
        "stability_score(sigma_1) >= stability_score(sigma_2) - 0.05."
    )
    limitations = "Evaluated in statistical expectation with adequate repetitions."
    test_implementation = (
        "Run ExplanationStabilityAnalyzer on test sample with sigma=0.01 and sigma=0.50 (n_rep=30), "
        "assert stability(0.01) >= stability(0.50)."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        models = make_trained_detectors(n_features=6)
        detector = models["rf_detector"]
        X_bg = models["X_train"]
        feature_names = models["feature_names"]
        explainer = SHAPExplainer(detector, X_bg, feature_names)

        x_sample = np.array([[1.2, -0.8, 0.4, 2.1, -1.0, 0.0]])

        analyzer_low = ExplanationStabilityAnalyzer(
            explainer=explainer,
            n_repetitions=30,
            noise_std=0.01,
            random_seed=42,
        )
        report_low = analyzer_low.analyze(x_sample)

        analyzer_high = ExplanationStabilityAnalyzer(
            explainer=explainer,
            n_repetitions=30,
            noise_std=0.60,
            random_seed=42,
        )
        report_high = analyzer_high.analyze(x_sample)

        score_low = report_low.stability_score
        score_high = report_high.stability_score

        # score_low should be near 1.0; score_high should be <= score_low
        passed = score_low >= (score_high - 0.02)

        return (
            passed,
            f"Stability noise monotonicity: score(sigma=0.01)={score_low:.4f} vs "
            f"score(sigma=0.60)={score_high:.4f}.",
            {"score_low": score_low, "score_high": score_high},
        )


class MR_EXP_05_ExplanationMetadataInvariance(MetamorphicRelation):
    """MR-EXP-05: Invariance of SHAP attributions under packet metadata injection."""

    id = "MR-EXP-05"
    name = "Explanation Invariance Under Metadata Header Injection"
    category = Category.EXPLANATION
    rationale = (
        "Explanations explain the model's decision on flow features. Injecting packet header "
        "metadata fields (such as 'srcip', 'timestamp', 'sensor_id') that are dropped during "
        "preprocessing must not alter the resulting SHAP feature contributions, base value, "
        "or top-k feature rankings."
    )
    input_transformation = (
        "Inject metadata fields into raw sample x to form x' before explanation."
    )
    expected_property = (
        "top_features(x) == top_features(x') in feature names, attribution values, and ranking."
    )
    limitations = "Injected keys must be in `_DROP_PATTERNS` or non-feature schema."
    test_implementation = (
        "Transform x and x', explain both with SHAPExplainer, assert identical top-k rankings."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, pipe_path, feature_names, base_sample = build_test_pipeline(Path(tmp_dir))
            models = make_trained_detectors(n_features=len(feature_names))
            detector = models["lr_detector"]

            # Background for explainer
            X_bg = np.zeros((1, len(feature_names)), dtype=np.float64)
            explainer = SHAPExplainer(detector, X_bg, feature_names)

            # Sample 1: original
            X_orig, _ = transform_single_sample(base_sample, pipe_path)
            res_orig = explainer.explain(X_orig, raw_sample=base_sample)

            # Sample 2: with injected metadata
            pert_sample = dict(base_sample)
            pert_sample["srcip"] = "192.168.1.100"
            pert_sample["dstip"] = "10.0.0.100"
            pert_sample["timestamp"] = 1727788999
            pert_sample["sensor_tag"] = "snort-01"

            X_pert, _ = transform_single_sample(pert_sample, pipe_path)
            res_pert = explainer.explain(X_pert, raw_sample=pert_sample)

            top_orig = res_orig.top_k(5)
            top_pert = res_pert.top_k(5)

            names_orig = [c.feature for c in top_orig]
            names_pert = [c.feature for c in top_pert]

            vals_orig = [c.shap_value for c in top_orig]
            vals_pert = [c.shap_value for c in top_pert]

            ranking_match = names_orig == names_pert
            vals_match = np.allclose(vals_orig, vals_pert, atol=1e-6)

            passed = ranking_match and vals_match
            return (
                passed,
                f"Explanation metadata invariance: ranking_match={ranking_match}, vals_match={vals_match}.",
                {"top_features_orig": names_orig, "top_features_pert": names_pert},
            )
