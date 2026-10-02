"""Reusable fixtures and synthetic generators for Metamorphic Testing."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    build_audit_record_hashes,
)
from backend.app.ml.models.logistic_regression import LogisticRegressionDetector
from backend.app.ml.models.random_forest import RandomForestDetector
from backend.app.ml.preprocessing.pipeline import build_preprocessing_pipeline


class DummyAuditRecord:
    """In-memory audit record matching the ledger verifier contract."""

    def __init__(
        self,
        sequence_number: int,
        id: str,
        payload_json: str,
        previous_hash: str,
        record_hash: str,
    ) -> None:
        self.sequence_number = sequence_number
        self.id = id
        self.payload_json = payload_json
        self.previous_hash = previous_hash
        self.record_hash = record_hash


def create_synthetic_flow_df(n_samples: int = 120, random_seed: int = 42) -> pd.DataFrame:
    """Generate a realistic synthetic network flow dataset with metadata."""
    rng = np.random.RandomState(random_seed)
    protocols = ["tcp", "udp", "icmp"]
    services = ["http", "dns", "ssh", "ftp", "unknown"]

    data = {
        # Metadata columns that should be dropped by pipeline
        "id": list(range(1, n_samples + 1)),
        "srcip": [f"192.168.1.{i % 250 + 1}" for i in range(n_samples)],
        "dstip": [f"10.0.0.{i % 100 + 1}" for i in range(n_samples)],
        "timestamp": [1700000000 + i * 10 for i in range(n_samples)],
        # Categorical features
        "proto": rng.choice(protocols, size=n_samples),
        "service": rng.choice(services, size=n_samples),
        # Numeric features
        "dur": rng.exponential(scale=1.2, size=n_samples),
        "sbytes": rng.randint(40, 65535, size=n_samples).astype(float),
        "dbytes": rng.randint(40, 65535, size=n_samples).astype(float),
        "sttl": rng.choice([64, 128, 255], size=n_samples).astype(float),
        "dttl": rng.choice([64, 128, 255], size=n_samples).astype(float),
        "sloss": rng.poisson(lam=1.5, size=n_samples).astype(float),
        "dloss": rng.poisson(lam=1.0, size=n_samples).astype(float),
        # Target binary label
        "label": rng.choice([0, 1], size=n_samples, p=[0.6, 0.4]),
    }
    return pd.DataFrame(data)


def build_test_pipeline(
    temp_dir: Path, random_seed: int = 42
) -> Tuple[Any, str, List[str], Dict[str, Any]]:
    """Build and fit a real preprocessing pipeline on synthetic data."""
    df = create_synthetic_flow_df(n_samples=120, random_seed=random_seed)
    res = build_preprocessing_pipeline(
        df=df,
        target_column="label",
        random_seed=random_seed,
        train_ratio=0.8,
        scaler_type="robust",
        save_dir=temp_dir,
        artifact_name="metamorphic_test",
    )
    # A representative sample dictionary matching the schema
    sample_row = df.iloc[0].to_dict()
    # Remove label
    sample_row.pop("label", None)

    return res, res.pipeline_path, res.feature_names, sample_row


def make_trained_detectors(
    n_features: int = 6, n_samples: int = 100, random_seed: int = 42
) -> Dict[str, Any]:
    """Create fitted LogisticRegression and RandomForest detectors."""
    rng = np.random.RandomState(random_seed)
    X = rng.randn(n_samples, n_features)
    # Make feature 0 strongly positive for class 1
    # Make feature 1 negative for class 1
    # Make feature 5 completely zero (null feature)
    X[:, 5] = 0.0
    logits = 2.5 * X[:, 0] - 1.8 * X[:, 1] + 0.5 * X[:, 2]
    probs = 1.0 / (1.0 + np.exp(-logits))
    y = (probs > 0.5).astype(int)

    feature_names = [f"net_metric_{i}" for i in range(n_features)]

    lr_detector = LogisticRegressionDetector(random_seed=random_seed)
    lr_detector.fit(X, y, feature_names=feature_names)

    rf_detector = RandomForestDetector(
        hyperparameters={"n_estimators": 15, "max_depth": 4},
        random_seed=random_seed,
    )
    rf_detector.fit(X, y, feature_names=feature_names)

    return {
        "lr_detector": lr_detector,
        "rf_detector": rf_detector,
        "X_train": X,
        "y_train": y,
        "feature_names": feature_names,
    }


def create_honest_chain(n_records: int = 5) -> List[DummyAuditRecord]:
    """Create an authentic forward-linked audit ledger."""
    records: List[DummyAuditRecord] = []
    prev_hash = GENESIS_PREVIOUS_HASH
    for seq in range(1, n_records + 1):
        payload = {
            "event_type": "INFERENCE",
            "prediction_id": f"pred-uuid-{seq}",
            "model_version": "v1.0.0",
            "features": {"f1": 1.2 * seq, "f2": 0.5},
            "predicted_class": "BENIGN" if seq % 2 == 1 else "ATTACK",
            "sequence": seq,
        }
        canon, p_hash, r_hash = build_audit_record_hashes(payload, prev_hash)
        records.append(
            DummyAuditRecord(
                sequence_number=seq,
                id=f"rec-{seq}",
                payload_json=canon,
                previous_hash=prev_hash,
                record_hash=r_hash,
            )
        )
        prev_hash = r_hash
    return records
