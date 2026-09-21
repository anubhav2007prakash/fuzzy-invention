"""Standalone CLI Runner for EXP-B: XAI Explanation Stability under Perturbation."""
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
    print("Running SentinelCrypt Research Benchmark: EXP-B")
    print("Title: XAI Explanation Stability under Gaussian Input Perturbation")
    print("=" * 70)

    svc = ExperimentService()
    result = svc.run_exp_b({"noise_levels": [0.01, 0.05, 0.10, 0.20], "n_repetitions": 8, "random_state": 42})

    curve = result["metrics"]["stability_curve"]
    mean_stab = result["metrics"]["overall_mean_stability"]

    print(f"\n[+] Noise Perturbation Curve (TreeSHAP on Random Forest):")
    print("    Noise sigma | Cosine Stability | Std Dev")
    print("    ------------+------------------+----------")
    for row in curve:
        print(f"     {row['noise_std']:<10.2f} |      {row['stability_score']:<11.4f} |    {row['std']:<8.4f}")

    print(f"\n[OK] Overall Mean Stability Score: {mean_stab:.4f}")
    print(f"[OK] Results successfully exported to results/exp_b_xai_stability.json\n")

if __name__ == "__main__":
    main()
