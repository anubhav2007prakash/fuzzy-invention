"""Standalone CLI Runner for EXP-C: Cryptographic Audit Ledger Integrity & Adversarial Attacks."""
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
    print("Running SentinelCrypt Research Benchmark: EXP-C")
    print("Title: Cryptographic Audit Ledger Integrity & Adversarial Attacks")
    print("=" * 70)

    svc = ExperimentService()
    result = svc.run_exp_c({"n_blocks": 50, "random_state": 42})

    metrics = result["metrics"]
    attacks = metrics["attacks_simulated"]
    tp = metrics["throughput"]

    print(f"\n[+] Clean Chain Mathematical Verification: {'VALID (PASS)' if metrics['clean_chain_valid'] else 'INVALID (FAIL)'}")
    print(f"[+] Overall Tamper Detection Rate:          {metrics['tamper_detection_rate']}")

    print("\n[!] Simulated Adversarial Attacks & Detection Localization:")
    for a in attacks:
        print(f"    - Attack:    {a['attack_type']}")
        print(f"      Tampered:  Sequence #{a['tampered_sequence']}")
        print(f"      Detected:  {a['detected']} (at Sequence #{a['detected_at_sequence']})")
        print(f"      Status:    {a['status']}\n")

    print(f"[+] Throughput & Overhead Benchmarks:")
    print(f"    - Total Build Time ({result['parameters']['n_blocks_evaluated']} blocks): {tp['total_chain_build_ms']:.2f} ms")
    print(f"    - Mean Append Latency:                {tp['mean_append_time_us']:.2f} us/block")
    print(f"    - Mean Verification Latency:          {tp['mean_verification_time_us']:.2f} us/block")

    print(f"\n[OK] Results successfully exported to results/exp_c_ledger_integrity.json\n")

if __name__ == "__main__":
    main()
