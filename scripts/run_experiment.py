"""Master CLI Runner for SentinelCrypt Research Experiments (EXP-A to EXP-D)."""
import argparse
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.experiment_service import ExperimentService

def run_all():
    print("=" * 80)
    print(" SENTINELCRYPT AI -- FULL RESEARCH BENCHMARK REPRODUCIBILITY SUITE")
    print(" Global Seed: random_state=42 | Protocol: Deterministic RFC 8785 + SHA-256")
    print("=" * 80)

    svc = ExperimentService()

    print("\n>>> [1/4] Executing EXP-A: Cross-Dataset Generalization...")
    res_a = svc.run_exp_a({"n_samples": 1200, "random_state": 42})
    gap = res_a["metrics"]["generalization_gap"]
    print(f"    [OK] In-Dist F1: {res_a['metrics']['in_distribution']['f1_score']*100:.2f}% | Out-Dist F1: {res_a['metrics']['out_of_distribution']['f1_score']*100:.2f}% | Delta F1: {gap['delta_f1']*100:.2f}%")

    print("\n>>> [2/4] Executing EXP-B: XAI Explanation Stability under Perturbation...")
    res_b = svc.run_exp_b({"noise_levels": [0.01, 0.05, 0.10, 0.20], "n_repetitions": 8, "random_state": 42})
    print(f"    [OK] Mean Cosine Stability Score: {res_b['metrics']['overall_mean_stability']:.4f}")

    print("\n>>> [3/4] Executing EXP-C: Cryptographic Audit Integrity & Adversarial Attacks...")
    res_c = svc.run_exp_c({"n_blocks": 50, "random_state": 42})
    print(f"    [OK] Clean Chain Valid: {res_c['metrics']['clean_chain_valid']} | Tamper Detection Rate: {res_c['metrics']['tamper_detection_rate']}")
    print(f"    [OK] Mean Verification Latency: {res_c['metrics']['throughput']['mean_verification_time_us']:.2f} us/block")

    print("\n>>> [4/4] Executing EXP-D: Model Architecture & Runtime Overhead Comparison...")
    res_d = svc.run_exp_d({"n_samples": 1500, "random_state": 42})
    comp = res_d["comparison"]
    print(f"    [OK] Logistic Regression F1: {comp['logistic_regression']['f1_score']*100:.2f}% (Infer: {comp['logistic_regression']['inference_time_us']:.2f} us)")
    print(f"    [OK] Random Forest F1:       {comp['random_forest']['f1_score']*100:.2f}% (Infer: {comp['random_forest']['inference_time_us']:.2f} us)")
    print(f"    [OK] Cryptographic Overhead: {comp['cryptographic_overhead']['canonicalization_and_sha256_us']:.2f} us/sample")

    print("\n" + "=" * 80)
    print(" [OK] ALL EXPERIMENTS COMPLETED SUCCESSFULLY! RESULTS PERSISTED TO results/")
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description="SentinelCrypt AI Experiment Runner")
    parser.add_argument("--exp", choices=["A", "B", "C", "D", "a", "b", "c", "d"], help="Run specific experiment (A, B, C, or D)")
    parser.add_argument("--all", action="store_true", help="Run all benchmark experiments sequentially")

    args = parser.parse_args()

    svc = ExperimentService()

    if args.all or not args.exp:
        run_all()
    else:
        exp_id = f"EXP-{args.exp.upper()}"
        print(f"Running {exp_id}...")
        res = svc.run_experiment_by_id(exp_id)
        print(f"[OK] {exp_id} Finished with status: {res.get('status')}")

if __name__ == "__main__":
    main()
