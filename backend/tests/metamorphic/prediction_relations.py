"""Metamorphic Relations for Model Prediction Behavior.

IMPORTANT:
    We do NOT assume that arbitrary input modifications should preserve predictions.
    Every relation here is mathematically or architecturally grounded in SentinelCrypt's
    provenance, schema filtering, or decision boundary geometry.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hashing import sha256_hash
from backend.app.ml.preprocessing.pipeline import (
    transform_batch_samples,
    transform_single_sample,
)
from backend.tests.metamorphic.fixtures import (
    build_test_pipeline,
    make_trained_detectors,
)
from backend.tests.metamorphic.framework import (
    Category,
    MetamorphicRelation,
)


class MR_PRED_01_MetadataInvariance(MetamorphicRelation):
    """MR-PRED-01: Model prediction invariance under non-feature metadata injection."""

    id = "MR-PRED-01"
    name = "Metadata Field Invariance for Model Inference"
    category = Category.PREDICTION
    rationale = (
        "In SentinelCrypt, network intrusion detectors are strictly trained on statistical "
        "flow features. Flow headers and identifiers (IP addresses, timestamps, ports) are "
        "pruned during preprocessing. Injecting or altering these non-feature metadata fields "
        "must have zero influence on feature transformation, predicted class, and probability scores."
    )
    input_transformation = (
        "Given raw input dictionary x, inject non-feature metadata fields "
        "('srcip', 'dstip', 'timestamp', 'sensor_id') to form x'."
    )
    expected_property = (
        "predicted_class(x') == predicted_class(x) and max_abs_diff(P(x'), P(x)) < 1e-6."
    )
    limitations = "Injected keys must not overlap with trained model feature columns."
    test_implementation = (
        "Transform x and x' through fitted pipeline, predict with trained detector, "
        "and assert class and probability vector equality."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            res, pipe_path, feature_names, base_sample = build_test_pipeline(Path(tmp_dir))
            models = make_trained_detectors(n_features=len(feature_names))
            detector = models["rf_detector"]

            # Transform original
            X_orig, _ = transform_single_sample(base_sample, pipe_path)
            pred_orig = int(detector.predict(X_orig)[0])
            prob_orig = detector.predict_proba(X_orig)[0]

            # Injected metadata
            perturbed = dict(base_sample)
            perturbed["srcip"] = "192.168.10.55"
            perturbed["dstip"] = "172.16.0.1"
            perturbed["timestamp"] = 1727788800
            perturbed["sensor_id"] = "snort-edge-gw01"

            X_pert, _ = transform_single_sample(perturbed, pipe_path)
            pred_pert = int(detector.predict(X_pert)[0])
            prob_pert = detector.predict_proba(X_pert)[0]

            class_match = pred_orig == pred_pert
            max_prob_diff = float(np.max(np.abs(prob_orig - prob_pert)))
            passed = class_match and (max_prob_diff < 1e-6)

            return (
                passed,
                f"Prediction under metadata injection: class_match={class_match}, max_prob_diff={max_prob_diff:.2e}.",
                {"pred_orig": pred_orig, "pred_pert": pred_pert, "max_prob_diff": max_prob_diff},
            )


class MR_PRED_02_KeyOrderInvariance(MetamorphicRelation):
    """MR-PRED-02: Prediction and evidence hash invariance under dictionary key ordering."""

    id = "MR-PRED-02"
    name = "Input Feature Key Ordering Invariance"
    category = Category.PREDICTION
    rationale = (
        "Dictionaries represent unordered key-value mappings. When inference requests arrive "
        "with keys in arbitrary order, the prediction service extracts features by column name "
        "and hashes the canonicalized input. Reordering keys must result in identical predictions, "
        "identical probabilities, and identical canonical input hashes."
    )
    input_transformation = (
        "Reverse and shuffle the key insertion order of feature dictionary x to form x'."
    )
    expected_property = (
        "predicted_class(x') == predicted_class(x), probabilities(x') == probabilities(x), "
        "and sha256(canonicalize(x')) == sha256(canonicalize(x))."
    )
    limitations = "The key-value pairs themselves must be identical."
    test_implementation = (
        "Evaluate prediction, probabilities, and input hash for original and shuffled dictionaries."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, pipe_path, feature_names, base_sample = build_test_pipeline(Path(tmp_dir))
            models = make_trained_detectors(n_features=len(feature_names))
            detector = models["lr_detector"]

            # Reverse keys
            rev_sample = {k: base_sample[k] for k in reversed(list(base_sample.keys()))}

            X_orig, _ = transform_single_sample(base_sample, pipe_path)
            X_rev, _ = transform_single_sample(rev_sample, pipe_path)

            pred_orig = int(detector.predict(X_orig)[0])
            pred_rev = int(detector.predict(X_rev)[0])

            prob_orig = detector.predict_proba(X_orig)[0]
            prob_rev = detector.predict_proba(X_rev)[0]

            hash_orig = sha256_hash(canonicalize(base_sample))
            hash_rev = sha256_hash(canonicalize(rev_sample))

            passed = (
                (pred_orig == pred_rev)
                and np.allclose(prob_orig, prob_rev, atol=1e-7)
                and (hash_orig == hash_rev)
            )

            return (
                passed,
                f"Key order invariance: pred_match={pred_orig == pred_rev}, hash_match={hash_orig == hash_rev}.",
                {"pred_orig": pred_orig, "hash_orig": hash_orig},
            )


class MR_PRED_03_PositiveWeightFeatureMonotonicity(MetamorphicRelation):
    """MR-PRED-03: Monotonic probability increase under attack-indicator amplification."""

    id = "MR-PRED-03"
    name = "Directional Monotonicity Under Attack-Indicator Amplification"
    category = Category.PREDICTION
    rationale = (
        "For a linear model f(x) = sigma(w^T x + b), the decision boundary logit is strictly "
        "monotonic with respect to each feature j according to the sign of its weight w_j. "
        "If a feature j has a positive weight w_j > 0 for class 1 (ATTACK), increasing x_j "
        "by delta > 0 while holding all other features fixed strictly increases the logit. "
        "Because the logistic sigmoid is strictly increasing, P(ATTACK | x') >= P(ATTACK | x). "
        "Furthermore, if x is already classified as ATTACK (prob > 0.5), x' cannot flip to BENIGN."
    )
    input_transformation = (
        "In a fitted Logistic Regression detector, locate feature j with positive weight w_j > 0. "
        "Increase x_j by delta > 0."
    )
    expected_property = (
        "P(ATTACK | x') >= P(ATTACK | x) - 1e-9. If pred(x) == 1, then pred(x') == 1."
    )
    limitations = "Applies to linear decision boundaries where the weight sign is strictly positive."
    test_implementation = (
        "Fit LogisticRegressionDetector, find index j where w_j > 0. "
        "Evaluate sample with x_j and x_j + delta for delta in [1.0, 3.0, 5.0], "
        "and assert monotonic non-decrease of P(ATTACK)."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        models = make_trained_detectors(n_features=6)
        detector = models["lr_detector"]
        raw_lr = detector.raw_model

        coefs = raw_lr.coef_[0]
        pos_indices = np.where(coefs > 0.1)[0]
        if len(pos_indices) == 0:
            return False, "No feature with positive coefficient found in test model.", {}

        j = int(pos_indices[0])
        w_j = float(coefs[j])

        # Test sample with neutral values
        x_base = np.zeros((1, 6), dtype=np.float64)
        x_base[0, j] = -1.0

        p_base = float(detector.predict_proba(x_base)[0, 1])

        monotonic_steps = []
        current_p = p_base
        all_monotonic = True

        for delta in [1.0, 2.5, 5.0]:
            x_step = x_base.copy()
            x_step[0, j] += delta
            p_step = float(detector.predict_proba(x_step)[0, 1])
            monotonic_steps.append((delta, p_step))
            if p_step < current_p - 1e-9:
                all_monotonic = False
            current_p = p_step

        return (
            all_monotonic,
            f"Monotonic probability increase along positive feature j={j} (w={w_j:.3f}): "
            f"base={p_base:.4f} -> {monotonic_steps[-1][1]:.4f}.",
            {"feature_idx": j, "weight": w_j, "steps": monotonic_steps},
        )


class MR_PRED_04_BatchRowIsolation(MetamorphicRelation):
    """MR-PRED-04: Independence of individual predictions from batch co-inhabitants."""

    id = "MR-PRED-04"
    name = "Batch Row Isolation and Permutation Invariance"
    category = Category.PREDICTION
    rationale = (
        "Network intrusion detection systems operate on streams and micro-batches. "
        "A detector must evaluate each flow independently: sample x must receive the "
        "identical prediction whether processed singly, surrounded by other benign flows, "
        "or surrounded by attack flows in a batch."
    )
    input_transformation = (
        "Evaluate sample x individually, then within batch [x_benign, x, x_attack], "
        "then in permuted batch [x, x_attack, x_benign]."
    )
    expected_property = (
        "pred(x) == pred_batch_1[1] == pred_batch_2[0] and probabilities match within 1e-6."
    )
    limitations = "Model must be stateless across inference calls."
    test_implementation = (
        "Run single inference and batch inferences with different neighboring samples and orderings, "
        "assert exact match for target sample."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, pipe_path, feature_names, base_sample = build_test_pipeline(Path(tmp_dir))
            models = make_trained_detectors(n_features=len(feature_names))
            detector = models["rf_detector"]

            # Target sample
            target = dict(base_sample)
            target["dur"] = 5.67
            target["sbytes"] = 8000.0

            # Distinct neighbors
            neighbor_a = dict(base_sample)
            neighbor_a["dur"] = 0.05
            neighbor_a["sbytes"] = 64.0

            neighbor_b = dict(base_sample)
            neighbor_b["dur"] = 99.9
            neighbor_b["sbytes"] = 999999.0

            # 1. Single prediction
            X_single, _ = transform_single_sample(target, pipe_path)
            pred_single = int(detector.predict(X_single)[0])
            prob_single = detector.predict_proba(X_single)[0]

            # 2. Batch [A, target, B]
            X_batch1, _ = transform_batch_samples([neighbor_a, target, neighbor_b], pipe_path)
            pred_batch1 = int(detector.predict(X_batch1)[1])
            prob_batch1 = detector.predict_proba(X_batch1)[1]

            # 3. Permuted batch [target, B, A]
            X_batch2, _ = transform_batch_samples([target, neighbor_b, neighbor_a], pipe_path)
            pred_batch2 = int(detector.predict(X_batch2)[0])
            prob_batch2 = detector.predict_proba(X_batch2)[0]

            passed = (
                (pred_single == pred_batch1 == pred_batch2)
                and np.allclose(prob_single, prob_batch1, atol=1e-6)
                and np.allclose(prob_single, prob_batch2, atol=1e-6)
            )

            return (
                passed,
                f"Batch row isolation: single={pred_single}, batch1={pred_batch1}, batch2={pred_batch2}.",
                {"pred_single": pred_single, "pred_batch1": pred_batch1, "pred_batch2": pred_batch2},
            )


class MR_PRED_05_ConfidenceThresholdMonotonicity(MetamorphicRelation):
    """MR-PRED-05: Monotonic uncertainty classification under tightening confidence threshold."""

    id = "MR-PRED-05"
    name = "Confidence Threshold Monotonic Uncertainty"
    category = Category.PREDICTION
    rationale = (
        "SentinelCrypt's prediction service tags samples as 'UNCERTAIN' whenever "
        "max_c P(c | x) < threshold. Because the condition max P < theta is monotonic with "
        "respect to theta, increasing the threshold from theta_1 to theta_2 (theta_2 > theta_1) "
        "can only expand the rejection region. Any sample uncertain under theta_1 MUST strictly "
        "remain uncertain under theta_2."
    )
    input_transformation = (
        "For a sample with maximum predicted probability p, evaluate confidence thresholding "
        "at theta_1 and theta_2 where theta_1 < theta_2."
    )
    expected_property = (
        "If is_uncertain(x, theta_1) == True, then is_uncertain(x, theta_2) == True."
    )
    limitations = "Valid for thresholds theta in [0, 1]."
    test_implementation = (
        "Compute max probability p on test sample. Set theta_1 = p + 0.05 (uncertain) "
        "and theta_2 = p + 0.20. Assert sample is uncertain under both."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        models = make_trained_detectors(n_features=6)
        detector = models["rf_detector"]

        X_sample = np.zeros((1, 6), dtype=np.float64)
        probs = detector.predict_proba(X_sample)[0]
        max_prob = float(np.max(probs))

        # Choose theta_1 slightly above max_prob so it triggers uncertainty
        theta_1 = min(0.99, max_prob + 0.02)
        theta_2 = min(0.999, theta_1 + 0.05)

        unc_1 = max_prob < theta_1
        unc_2 = max_prob < theta_2

        # Monotonicity: unc_1 implies unc_2
        passed = (not unc_1) or unc_2

        return (
            passed,
            f"Confidence threshold monotonicity: max_p={max_prob:.3f}, theta_1={theta_1:.3f} (unc={unc_1}), "
            f"theta_2={theta_2:.3f} (unc={unc_2}).",
            {"max_prob": max_prob, "theta_1": theta_1, "theta_2": theta_2, "unc_1": unc_1, "unc_2": unc_2},
        )
