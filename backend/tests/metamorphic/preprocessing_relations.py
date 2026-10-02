"""Metamorphic Relations for Feature Preprocessing Pipeline."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from backend.app.ml.preprocessing.pipeline import (
    transform_batch_samples,
    transform_single_sample,
)
from backend.tests.metamorphic.fixtures import build_test_pipeline
from backend.tests.metamorphic.framework import (
    Category,
    MetamorphicRelation,
)


class MR_PRE_01_MetadataInvariance(MetamorphicRelation):
    """MR-PRE-01: Invariance under packet/flow metadata field modification."""

    id = "MR-PRE-01"
    name = "Metadata Field Dropping Invariance"
    category = Category.PREPROCESSING
    rationale = (
        "In network intrusion detection, packet captures routinely carry metadata "
        "(source/destination IP addresses, ports, sequence IDs, packet arrival timestamps). "
        "SentinelCrypt's preprocessing pipeline drops these headers based on `_DROP_PATTERNS` "
        "to avoid shortcut learning and data leakage. Injecting, deleting, or altering "
        "metadata fields outside the trained feature schema must have zero effect on the "
        "transformed numerical representation."
    )
    input_transformation = (
        "Given sample dictionary x, inject metadata fields (e.g. 'srcip', 'dstip', 'timestamp', "
        "'custom_audit_id') to form x'."
    )
    expected_property = "T(x) == T(x') element-wise within 1e-9 tolerance."
    limitations = "Injected keys must strictly be outside the trained feature schema (feature_cols)."
    test_implementation = (
        "Transform x and x' using `transform_single_sample` with a fitted pipeline and assert "
        "`np.allclose(X_orig, X_perturbed, atol=1e-9)`."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, pipe_path, feature_names, base_sample = build_test_pipeline(Path(tmp_dir))

            # Transform original
            x_orig, _ = transform_single_sample(base_sample, pipe_path)

            # Follow-up: add arbitrary metadata
            perturbed = dict(base_sample)
            perturbed["srcip"] = "192.168.1.99"
            perturbed["dstip"] = "10.0.0.99"
            perturbed["timestamp"] = 9999999999
            perturbed["custom_sensor_id"] = "sensor-edge-01"
            perturbed["uid"] = "flow-999-alpha"

            x_pert, _ = transform_single_sample(perturbed, pipe_path)

            max_diff = float(np.max(np.abs(x_orig - x_pert)))
            is_identical = np.allclose(x_orig, x_pert, atol=1e-9)

            return (
                is_identical,
                f"Transformed features are {'identical' if is_identical else 'different'} (max abs diff: {max_diff:.2e}).",
                {"max_abs_diff": max_diff, "num_features": len(feature_names)},
            )


class MR_PRE_02_DictOrderInvariance(MetamorphicRelation):
    """MR-PRE-02: Invariance under dictionary key insertion order permutation."""

    id = "MR-PRE-02"
    name = "Dictionary Key Insertion Order Invariance"
    category = Category.PREPROCESSING
    rationale = (
        "A Python dictionary is conceptually an unordered mapping. Feature extraction "
        "must be governed solely by the model's frozen schema (`feature_cols`), completely "
        "independent of the in-memory iteration or insertion order of keys."
    )
    input_transformation = (
        "Construct x' by reversing and randomizing the insertion order of keys in dictionary x."
    )
    expected_property = "T(x) == T(x') element-wise."
    limitations = "Applies to dictionary-based feature inputs; array inputs have semantic order."
    test_implementation = (
        "Construct reversed and shuffled dictionaries of x, transform each, and verify exact array equality."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, pipe_path, feature_names, base_sample = build_test_pipeline(Path(tmp_dir))

            x_orig, _ = transform_single_sample(base_sample, pipe_path)

            # Follow-up: reversed key order
            reversed_sample = {k: base_sample[k] for k in reversed(list(base_sample.keys()))}
            x_rev, _ = transform_single_sample(reversed_sample, pipe_path)

            # Follow-up: shuffled key order
            keys = list(base_sample.keys())
            np.random.RandomState(1337).shuffle(keys)
            shuffled_sample = {k: base_sample[k] for k in keys}
            x_shuf, _ = transform_single_sample(shuffled_sample, pipe_path)

            diff_rev = float(np.max(np.abs(x_orig - x_rev)))
            diff_shuf = float(np.max(np.abs(x_orig - x_shuf)))

            passed = (diff_rev == 0.0) and (diff_shuf == 0.0)
            return (
                passed,
                f"Feature extraction is {'invariant' if passed else 'variant'} to dictionary key ordering.",
                {"max_diff_reversed": diff_rev, "max_diff_shuffled": diff_shuf},
            )


class MR_PRE_03_UnseenCategoricalEquivalence(MetamorphicRelation):
    """MR-PRE-03: Equivalence of out-of-vocabulary categorical fallback tokens."""

    id = "MR-PRE-03"
    name = "Out-of-Vocabulary Categorical Fallback Equivalence"
    category = Category.PREPROCESSING
    rationale = (
        "When processing network traffic with novel protocol variants or unobserved service names, "
        "the pipeline maps unknown categories to the fallback index -1 (via `_encode_categoricals`). "
        "Any two distinct out-of-vocabulary tokens for the same categorical field must produce "
        "the exact same encoded and scaled values."
    )
    input_transformation = (
        "Replace an unseen categorical token v1 with another unseen categorical token v2 for feature c."
    )
    expected_property = "T(x[c=v1]) == T(x[c=v2]) element-wise."
    limitations = "Both categorical tokens must be completely absent from the training vocabulary."
    test_implementation = (
        "Set proto to 'CUSTOM_PROTO_A' in x1 and 'RESERVED_PROTO_B' in x2. "
        "Transform both with `transform_single_sample` and check equality."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, pipe_path, _, base_sample = build_test_pipeline(Path(tmp_dir))

            sample_v1 = dict(base_sample)
            sample_v1["proto"] = "CUSTOM_PROTOCOL_FOO_99"

            sample_v2 = dict(base_sample)
            sample_v2["proto"] = "UNKNOWN_EXPERIMENTAL_BAR_42"

            x_v1, _ = transform_single_sample(sample_v1, pipe_path)
            x_v2, _ = transform_single_sample(sample_v2, pipe_path)

            max_diff = float(np.max(np.abs(x_v1 - x_v2)))
            passed = max_diff == 0.0

            return (
                passed,
                f"Out-of-vocabulary fallback produces {'identical' if passed else 'divergent'} vectors.",
                {"max_abs_diff": max_diff},
            )


class MR_PRE_04_BatchIsolationConsistency(MetamorphicRelation):
    """MR-PRE-04: Independence of single vs batch inference transformations."""

    id = "MR-PRE-04"
    name = "Batch Inference Isolation / Stateless Preprocessing"
    category = Category.PREPROCESSING
    rationale = (
        "In production, inference samples arrive individually (API) or in bulk (batch). "
        "Because preprocessing at test time uses frozen parameters (training median, scaling centers), "
        "transforming a sample individually must yield the identical vector as transforming it "
        "surrounded by arbitrary other samples in a batch. No inter-sample cross-talk may exist."
    )
    input_transformation = (
        "Given target sample x_i and companion samples x_1, x_2, transform x_i via "
        "`transform_single_sample(x_i)` versus as part of batch [x_1, x_i, x_2] via `transform_batch_samples`."
    )
    expected_property = "T_single(x_i) == T_batch(X)[1] within 1e-9 tolerance."
    limitations = "Requires the exact same serialized pipeline artifact for both calls."
    test_implementation = (
        "Transform sample alone and within a heterogeneous 3-sample batch, assert `np.allclose`."
    )

    def evaluate(self, **kwargs: Any) -> Tuple[bool, str, Dict[str, Any]]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, pipe_path, _, base_sample = build_test_pipeline(Path(tmp_dir))

            # Sample 1: original
            s1 = dict(base_sample)
            # Sample 2: target sample with distinct values
            target = dict(base_sample)
            target["dur"] = 12.34
            target["sbytes"] = 54321.0
            target["proto"] = "udp"
            # Sample 3: another distinct sample
            s3 = dict(base_sample)
            s3["dur"] = 0.001
            s3["sbytes"] = 64.0

            x_single, _ = transform_single_sample(target, pipe_path)
            x_batch, _ = transform_batch_samples([s1, target, s3], pipe_path)

            x_batch_target = x_batch[1:2]
            max_diff = float(np.max(np.abs(x_single - x_batch_target)))
            passed = np.allclose(x_single, x_batch_target, atol=1e-9)

            return (
                passed,
                f"Batch vs single transformation {'matched exactly' if passed else 'diverged'} (max diff: {max_diff:.2e}).",
                {"max_abs_diff": max_diff},
            )
