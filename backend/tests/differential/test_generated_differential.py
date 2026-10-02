"""Seeded generated differential cases for SentinelCrypt's critical paths."""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import train_test_split

from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    build_audit_record_hashes,
    calculate_payload_hash,
)
from backend.app.cryptography.hashing import sha256_hash
from backend.app.cryptography.reference.chain import (
    GENESIS,
    verify_chain,
)
from backend.app.cryptography.reference import (
    ref_canonical_json,
    ref_payload_hash,
    ref_record_hash,
)
from backend.app.cryptography.verifier import verify_ledger
from backend.app.ml.evaluation.metrics import compute_metrics
from backend.app.ml.preprocessing.pipeline import build_preprocessing_pipeline


_SEED = 20261001
_UNICODE = ("audit", "café", "こんにちは", "🔐", "line\nbreak", "")


@dataclass
class _GeneratedRecord:
    sequence_number: int
    payload_json: str
    payload_hash: str
    previous_hash: str
    record_hash: str
    id: str


def _generated_json_value(rng: random.Random, depth: int = 0) -> Any:
    if depth >= 3:
        choices = (
            None,
            True,
            False,
            rng.randint(-(2**52), 2**52),
            rng.uniform(-1e6, 1e6),
            rng.choice(_UNICODE),
        )
        return rng.choice(choices)
    container = rng.randrange(4)
    if container == 0:
        return [
            _generated_json_value(rng, depth + 1)
            for _ in range(rng.randrange(5))
        ]
    if container == 1:
        return {
            f"k{index}_{rng.randrange(100)}": _generated_json_value(rng, depth + 1)
            for index in range(rng.randrange(5))
        }
    return _generated_json_value(rng, 3)


def _assert_equal(component: str, case: str, production: Any, reference: Any) -> None:
    assert production == reference, (
        f"{component} differential mismatch for seed={_SEED}, case={case}\n"
        f"production: {production!r}\n"
        f"reference:  {reference!r}"
    )


def test_generated_canonical_json_matches_independent_serializer():
    rng = random.Random(_SEED)
    for case_number in range(250):
        payload = {
            f"field_{index}_{rng.randrange(1000)}": _generated_json_value(rng)
            for index in range(rng.randrange(1, 8))
        }
        production = canonicalize(payload)
        reference = ref_canonical_json(payload)
        _assert_equal("canonicalization", str(case_number), production, reference)
        assert json.loads(production) == payload, (
            f"canonicalization round-trip failed for seed={_SEED}, "
            f"case={case_number}, payload={payload!r}"
        )


def test_generated_sha256_strings_and_bytes_match_hashlib():
    rng = random.Random(_SEED)
    for case_number in range(250):
        size = rng.randrange(513)
        data = bytes(rng.getrandbits(8) for _ in range(size))
        _assert_equal(
            "SHA-256 bytes",
            str(case_number),
            sha256_hash(data),
            hashlib.sha256(data).hexdigest(),
        )

        text = "".join(rng.choice(_UNICODE) for _ in range(rng.randrange(20)))
        _assert_equal(
            "SHA-256 UTF-8 string",
            str(case_number),
            sha256_hash(text),
            hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )


def _record(sequence: int, payload: dict[str, Any], previous_hash: str):
    canonical, payload_hash, record_hash = build_audit_record_hashes(
        payload, previous_hash=previous_hash
    )
    return _GeneratedRecord(
        sequence, canonical, payload_hash, previous_hash, record_hash,
        f"generated-{sequence}",
    )


def test_generated_hash_chain_construction_matches_reference():
    rng = random.Random(_SEED)
    for case_number in range(200):
        payload = {
            "case": case_number,
            "body": _generated_json_value(rng),
            "sequence": rng.randrange(1, 1_000_000),
        }
        previous_hash = "".join(rng.choice("0123456789abcdef") for _ in range(64))
        production_payload_hash = calculate_payload_hash(payload)
        reference_payload_hash = ref_payload_hash(payload)
        _assert_equal(
            "payload hash", str(case_number),
            production_payload_hash, reference_payload_hash,
        )
        production_record_hash = build_audit_record_hashes(
            payload, previous_hash=previous_hash
        )[2]
        reference_record_hash = ref_record_hash(
            previous_hash, reference_payload_hash
        )
        _assert_equal(
            "record hash", str(case_number),
            production_record_hash, reference_record_hash,
        )


def test_generated_valid_and_tampered_ledgers_agree_with_reference():
    rng = random.Random(_SEED)
    for case_number in range(1, 41):
        records = []
        previous_hash = GENESIS_PREVIOUS_HASH
        for sequence in range(1, case_number + 1):
            payload = {
                "sequence": sequence,
                "value": rng.uniform(-1000, 1000),
                "tag": rng.choice(_UNICODE),
            }
            record = _record(sequence, payload, previous_hash)
            records.append(record)
            previous_hash = record.record_hash

        shuffled = list(records)
        rng.shuffle(shuffled)
        reference_valid, reference_errors = verify_chain([
            {
                "sequence_number": item.sequence_number,
                "payload_json": item.payload_json,
                "payload_hash": item.payload_hash,
                "previous_hash": item.previous_hash,
                "record_hash": item.record_hash,
            }
            for item in shuffled
        ])
        actual_valid = verify_ledger(shuffled).verified
        _assert_equal("ledger verification (valid)", str(case_number),
                      actual_valid, reference_valid)
        assert actual_valid is True, (
            f"valid generated ledger rejected: seed={_SEED}, "
            f"records={case_number}, errors={reference_errors}"
        )

        damaged = list(records)
        victim = damaged[case_number // 2]
        damaged[case_number // 2] = type(victim)(
            victim.sequence_number,
            json.dumps({"modified": case_number}),
            victim.payload_hash,
            victim.previous_hash,
            victim.record_hash,
            victim.id,
        )
        reference_valid, reference_errors = verify_chain([
            {
                "sequence_number": item.sequence_number,
                "payload_json": item.payload_json,
                "payload_hash": item.payload_hash,
                "previous_hash": item.previous_hash,
                "record_hash": item.record_hash,
            }
            for item in damaged
        ])
        actual_damaged = verify_ledger(damaged).verified
        _assert_equal("ledger verification (tampered)", str(case_number),
                      actual_damaged, reference_valid)
        assert actual_damaged is False, (
            f"tampered generated ledger accepted: seed={_SEED}, "
            f"records={case_number}"
        )


def _reference_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Closed-form macro metrics using Python counts, independent of sklearn."""
    labels = sorted(set(y_true.tolist()) | set(y_pred.tolist()))
    total = len(y_true)
    accuracy = sum(a == b for a, b in zip(y_true, y_pred)) / total
    precisions = []
    recalls = []
    f1s = []
    for label in labels:
        tp = sum(a == label and b == label for a, b in zip(y_true, y_pred))
        fp = sum(a != label and b == label for a, b in zip(y_true, y_pred))
        fn = sum(a == label and b != label for a, b in zip(y_true, y_pred))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)
    return {
        "accuracy": accuracy,
        "precision_macro": sum(precisions) / len(precisions),
        "recall_macro": sum(recalls) / len(recalls),
        "f1_macro": sum(f1s) / len(f1s),
    }


def test_generated_classification_metrics_match_closed_form_reference():
    rng = np.random.default_rng(_SEED)
    for case_number in range(100):
        n_classes = int(rng.integers(2, 6))
        size = int(rng.integers(30, 301))
        y_true = rng.integers(0, n_classes, size=size)
        y_pred = rng.integers(0, n_classes, size=size)
        production = compute_metrics(y_true, y_pred)
        reference = _reference_metrics(y_true, y_pred)
        for metric_name, reference_value in reference.items():
            actual = production[metric_name]
            assert actual == pytest.approx(reference_value, abs=1e-12), (
                f"metrics differential mismatch: seed={_SEED}, case={case_number}, "
                f"metric={metric_name}, production={actual}, "
                f"reference={reference_value}, classes={n_classes}, size={size}"
            )


def _reference_preprocess(
    frame: pd.DataFrame,
    seed: int,
    train_ratio: float,
    scaler_type: str,
):
    """Small independent numeric/categorical transform for controlled fixtures."""
    labels = sorted({str(value) for value in frame["label"]})
    label_ids = {label: index for index, label in enumerate(labels)}
    y = np.asarray([label_ids[str(value)] for value in frame["label"]])
    features = frame[["numeric_a", "numeric_b", "category"]].copy()
    train, test, y_train, y_test = train_test_split(
        features,
        y,
        test_size=1.0 - train_ratio,
        random_state=seed,
        stratify=y,
    )

    def encode(split: pd.DataFrame, training: pd.DataFrame) -> np.ndarray:
        columns = []
        for name in ("numeric_a", "numeric_b"):
            values = split[name].to_numpy(dtype=np.float64, copy=True)
            values[~np.isfinite(values)] = np.nan
            columns.append(values)
        train_categories = sorted({str(value) for value in training["category"]})
        category_ids = {value: index for index, value in enumerate(train_categories)}
        columns.append(np.asarray(
            [category_ids.get(str(value), -1) for value in split["category"]],
            dtype=np.float64,
        ))
        return np.column_stack(columns)

    train_matrix = encode(train, train)
    test_matrix = encode(test, train)
    medians = np.nanmedian(train_matrix, axis=0)
    for column in range(train_matrix.shape[1]):
        train_missing = np.isnan(train_matrix[:, column])
        test_missing = np.isnan(test_matrix[:, column])
        train_matrix[train_missing, column] = medians[column]
        test_matrix[test_missing, column] = medians[column]

    if scaler_type == "robust":
        centers = np.median(train_matrix, axis=0)
        low, high = np.percentile(train_matrix, [25, 75], axis=0)
        scales = high - low
    else:
        centers = np.mean(train_matrix, axis=0)
        scales = np.std(train_matrix, axis=0)
    scales = np.where(np.abs(scales) < np.finfo(np.float64).eps * 10, 1.0, scales)
    return (
        (train_matrix - centers) / scales,
        (test_matrix - centers) / scales,
        y_train,
        y_test,
    )


@pytest.mark.parametrize("scaler_type", ["robust", "standard"])
@pytest.mark.parametrize("seed", [0, 7, 42, 2026, 8675309])
def test_generated_preprocessing_matches_independent_reference(
    tmp_path, scaler_type: str, seed: int
):
    rng = np.random.default_rng(seed)
    size = 120
    frame = pd.DataFrame({
        "numeric_a": rng.normal(loc=4.0, scale=3.0, size=size),
        "numeric_b": rng.uniform(-20.0, 50.0, size=size),
        "category": rng.choice(["tcp", "udp", "icmp"], size=size),
        "label": np.tile(["benign", "attack"], size // 2),
    })
    frame.loc[[3, 17], "numeric_a"] = np.nan
    frame.loc[[8, 91], "numeric_a"] = np.inf
    frame.loc[[22, 67], "numeric_b"] = -np.inf
    frame.loc[0, "category"] = "rare-category"

    expected = _reference_preprocess(frame, seed, 0.8, scaler_type)
    result = build_preprocessing_pipeline(
        frame,
        target_column="label",
        random_seed=seed,
        train_ratio=0.8,
        scaler_type=scaler_type,
        save_dir=tmp_path,
        artifact_name=f"generated-{scaler_type}-{seed}",
    )
    for name, actual, reference in zip(
        ("X_train", "X_test", "y_train", "y_test"),
        (result.X_train, result.X_test, result.y_train, result.y_test),
        expected,
    ):
        if actual.shape != reference.shape:
            raise AssertionError(
                f"preprocessing differential shape mismatch: seed={seed}, "
                f"scaler={scaler_type}, output={name}, "
                f"production_shape={actual.shape}, reference_shape={reference.shape}"
            )
        try:
            np.testing.assert_allclose(actual, reference, rtol=1e-10, atol=1e-10)
        except AssertionError as exc:
            delta = np.abs(np.asarray(actual) - np.asarray(reference))
            raise AssertionError(
                f"preprocessing differential mismatch: seed={seed}, "
                f"scaler={scaler_type}, output={name}, "
                f"max_abs_diff={np.nanmax(delta):.12g}, detail={exc}"
            ) from exc
