"""Standalone CLI Runner for EXP-D: Model Architecture & Runtime Overhead Comparison."""
import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.experiment_service import ExperimentService

def main():
    print("=" * 70)
    print("Running SentinelCrypt Research Benchmark: EXP-D")
    print("Title: Model Architecture & Runtime Overhead Comparison")
    print("=" * 70)

    svc = ExperimentService()
    result = svc.run_exp_d({"n_samples": 1500, "random_state": 42})

    comp = result["comparison"]
    lr = comp["logistic_regression"]
    rf = comp["random_forest"]
    crypto = comp["cryptographic_overhead"]

    print("\n[+] Direct Comparison: Logistic Regression vs Random Forest:")
    print("    Metric              | Logistic Regression | Random Forest")
    print("    --------------------+---------------------+------------------")
    print(f"    Accuracy            | {lr['accuracy']*100:<19.2f}% | {rf['accuracy']*100:<16.2f}%")
    print(f"    F1-Score            | {lr['f1_score']*100:<19.2f}% | {rf['f1_score']*100:<16.2f}%")
    print(f"    ROC-AUC             | {lr['roc_auc']:<20.4f} | {rf['roc_auc']:<17.4f}")
    print(f"    Training Time (ms)  | {lr['training_time_ms']:<20.2f} | {rf['training_time_ms']:<17.2f}")
    print(f"    Inference Time (us) | {lr['inference_time_us']:<20.2f} | {rf['inference_time_us']:<17.2f}")

    print("\n[+] Cryptographic Anchoring Overhead:")
    print(f"    - Canonicalization + SHA-256: {crypto['canonicalization_and_sha256_us']:.2f} us/sample")
    print(f"    - Relative Pipeline Impact:   {crypto['relative_overhead_pct']}")

    print(f"\n[OK] Results successfully exported to results/exp_d_model_comparison.json\n")

if __name__ == "__main__":
    main()
