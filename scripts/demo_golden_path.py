#!/usr/bin/env python3
"""SentinelCrypt AI — Golden Path Demo Script.

Runs the complete pipeline end-to-end:
  1. Generate synthetic dataset
  2. Upload and validate
  3. Train Random Forest model
  4. Run predictions (benign + attack)
  5. Generate SHAP explanations
  6. Verify audit ledger integrity

Usage:
  python scripts/demo_golden_path.py

Prerequisites:
  - Backend running on http://localhost:8000
  - pip install requests
"""
import json
import sys
import tempfile
import time
from pathlib import Path

# Windows consoles may default to cp1252, which cannot encode arrows/check marks.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests")
    sys.exit(1)

import numpy as np
import pandas as pd

BASE_URL = "http://localhost:8000/api/v1"


def step(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def generate_synthetic_dataset(n_rows: int = 500) -> Path:
    """Generate a synthetic network flow CSV dataset."""
    rng = np.random.RandomState(42)

    n_attack = int(n_rows * 0.3)
    n_benign = n_rows - n_attack

    data = {
        "dur": list(rng.exponential(0.5, n_benign)) + list(rng.exponential(0.05, n_attack)),
        "spkts": list(rng.poisson(10, n_benign) + 1) + list(rng.poisson(45, n_attack) + 10),
        "dpkts": list(rng.poisson(12, n_benign)) + list(rng.poisson(2, n_attack)),
        "sbytes": list(rng.randint(60, 500, n_benign)) + list(rng.randint(40, 100, n_attack)),
        "dbytes": list(rng.randint(60, 1500, n_benign)) + list(rng.randint(0, 100, n_attack)),
        "rate": [0]*n_benign + [0]*n_attack,  # computed below
        "sttl": list(rng.choice([64, 128], n_benign)) + list(rng.choice([254, 255], n_attack)),
        "dttl": list(rng.choice([64, 128], n_benign)) + list(rng.choice([0, 32], n_attack)),
        "label": [0]*n_benign + [1]*n_attack,
    }
    # Compute rate
    data["rate"] = [
        (s + d) / (max(dur, 0.001))
        for s, d, dur in zip(data["spkts"], data["dpkts"], data["dur"])
    ]

    df = pd.DataFrame(data).sample(frac=1, random_state=42).reset_index(drop=True)
    path = Path(tempfile.mktemp(suffix=".csv"))
    df.to_csv(path, index=False)
    return path


def main():
    print("SentinelCrypt AI — Golden Path Demo")
    print("This script demonstrates the complete pipeline:")
    print("  Dataset Upload → Model Training → Prediction → XAI → Audit Verification")

    # Check backend is running
    step("0. Checking backend connectivity")
    try:
        r = requests.get(f"{BASE_URL}/../..", timeout=5)
        r.raise_for_status()
        print(f"  Backend: {r.json()['service']} ✅")
    except Exception as e:
        print(f"  ERROR: Backend not reachable at {BASE_URL}")
        print(f"  Start with: uvicorn backend.app.main:app --reload --port 8000")
        sys.exit(1)

    # Step 1: Generate dataset
    step("1. Generating synthetic network flow dataset")
    csv_path = generate_synthetic_dataset(500)
    print(f"  Generated: {csv_path.name} (500 rows, 9 features)")

    # Step 2: Upload dataset
    step("2. Uploading and validating dataset")
    with open(csv_path, "rb") as f:
        files = {"file": ("demo_flows.csv", f, "text/csv")}
        data = {"dataset_name": "Demo Network Flows"}
        r = requests.post(f"{BASE_URL}/datasets", files=files, data=data)
    r.raise_for_status()
    result = r.json()
    dataset_id = result["dataset_id"]
    val = result["validation"]
    print(f"  Dataset ID: {dataset_id}")
    print(f"  Rows: {val['row_count']}, Features: {val['feature_count']}")
    print(f"  Format: {val['detected_format']}")

    # Step 3: Train model
    step("3. Training Random Forest model")
    r = requests.post(f"{BASE_URL}/models/train", json={
        "dataset_id": dataset_id,
        "model_type": "random_forest",
        "random_seed": 42,
    })
    r.raise_for_status()
    model = r.json()
    model_id = model["id"]
    metrics = model.get("metrics", {})
    print(f"  Model ID: {model_id}")
    print(f"  Accuracy: {metrics.get('accuracy', 'N/A')}")
    print(f"  F1-Macro: {metrics.get('f1_macro', 'N/A')}")

    # Step 4: Run predictions
    step("4. Running predictions (benign + attack samples)")
    # Sample from the dataset for realistic features
    df = pd.read_csv(csv_path)
    benign_sample = df[df["label"] == 0].iloc[0].drop("label").to_dict()
    attack_sample = df[df["label"] == 1].iloc[0].drop("label").to_dict()

    # Benign prediction
    r = requests.post(f"{BASE_URL}/predictions", json={
        "model_id": model_id,
        "features": {k: float(v) for k, v in benign_sample.items()},
    })
    r.raise_for_status()
    benign_pred = r.json()
    print(f"  Benign sample → {benign_pred['predicted_class']} (confidence: {benign_pred.get('probabilities', {})})")

    # Attack prediction
    r = requests.post(f"{BASE_URL}/predictions", json={
        "model_id": model_id,
        "features": {k: float(v) for k, v in attack_sample.items()},
    })
    r.raise_for_status()
    attack_pred = r.json()
    print(f"  Attack sample → {attack_pred['predicted_class']} (confidence: {attack_pred.get('probabilities', {})})")

    # Step 5: Generate SHAP explanation
    step("5. Generating SHAP explanation for attack prediction")
    r = requests.post(
        f"{BASE_URL}/explanations/{attack_pred['prediction_id']}",
        json={"top_k": 5, "compute_stability": True, "n_repetitions": 5},
    )
    r.raise_for_status()
    explanation = r.json()
    print(f"  Method: {explanation['method']}")
    print(f"  Stability score: {explanation.get('stability_score', 'N/A')}")
    print(f"  Top features:")
    for feat in explanation.get("top_features", [])[:5]:
        print(f"    {feat['feature']}: SHAP={feat['shap_value']:.4f} (importance={feat['importance']:.4f})")

    # Step 6: Verify audit ledger
    step("6. Verifying cryptographic audit ledger integrity")
    r = requests.post(f"{BASE_URL}/audit/verify", json={"verify_entire_chain": True})
    r.raise_for_status()
    verification = r.json()
    print(f"  Records verified: {verification.get('checked_records', 0)}")
    print(f"  Tamper detected: {verification.get('tamper_detected', False)}")
    print(f"  Message: {verification.get('message', '')}")

    # Ledger status
    r = requests.get(f"{BASE_URL}/audit/status")
    r.raise_for_status()
    status = r.json()
    print(f"  Total records: {status['total_records']}")
    print(f"  Latest sequence: {status['latest_sequence']}")
    print(f"  Chain intact: {status['is_intact']}")

    # Cleanup
    csv_path.unlink(missing_ok=True)

    step("Demo complete! ✅")
    print("\nAll steps passed. The SentinelCrypt pipeline is working correctly.")
    print("Open http://localhost:5173 to explore the dashboard.")


if __name__ == "__main__":
    main()
