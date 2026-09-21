"""Standalone CLI Runner for EXP-A: Cross-Dataset Generalization."""
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
    print("Running SentinelCrypt Research Benchmark: EXP-A")
    print("Title: Cross-Dataset Generalization (Generalization Gap)")
    print("=" * 70)

    svc = ExperimentService()
    result = svc.run_exp_a({"n_samples": 1500, "random_state": 42})

    in_dist = result["metrics"]["in_distribution"]
    out_dist = result["metrics"]["out_of_distribution"]
    gap = result["metrics"]["generalization_gap"]

    print(f"\n[+] In-Distribution ({in_dist['dataset']}):")
    print(f"    Accuracy:  {in_dist['accuracy']*100:.2f}%")
    print(f"    F1-Score:  {in_dist['f1_score']*100:.2f}%")
    print(f"    Precision: {in_dist['precision']*100:.2f}%")
    print(f"    Recall:    {in_dist['recall']*100:.2f}%")
    print(f"    ROC-AUC:   {in_dist['roc_auc']:.4f}")

    print(f"\n[+] Out-of-Distribution ({out_dist['dataset']}):")
    print(f"    Accuracy:  {out_dist['accuracy']*100:.2f}%")
    print(f"    F1-Score:  {out_dist['f1_score']*100:.2f}%")
    print(f"    Precision: {out_dist['precision']*100:.2f}%")
    print(f"    Recall:    {out_dist['recall']*100:.2f}%")
    print(f"    ROC-AUC:   {out_dist['roc_auc']:.4f}")

    print(f"\n[!] Generalization Gap:")
    print(f"    Delta F1-Score:  {gap['delta_f1']*100:.2f}%")
    print(f"    Delta Accuracy:  {gap['delta_accuracy']*100:.2f}%")
    print(f"    Status:          {result['status']}")
    print(f"\n[OK] Results successfully exported to results/exp_a_cross_dataset.json\n")

if __name__ == "__main__":
    main()
