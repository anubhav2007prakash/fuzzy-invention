#!/usr/bin/env python3
"""SentinelCrypt one-command experiment CLI (item 22).

    python scripts/sentinel.py experiment run EXP-B
    python scripts/sentinel.py experiment run EXP-B --config '{"n_repetitions": 4}'
    python scripts/sentinel.py benchmark run
    python scripts/sentinel.py challenge run --preset Q1
    python scripts/sentinel.py verify-artifact path/to/artifact.json

`experiment run` executes the full research workflow:
    validate config -> run -> generate explanations (where applicable)
    -> cryptographic evidence -> verify evidence -> save results
    -> reproducibility package -> report.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _banner(step: str, total: int, msg: str) -> None:
    print(f"\n[{step}/{total}] {msg}")


def cmd_experiment_run(args: argparse.Namespace) -> int:
    from backend.app.services.experiment_service import ExperimentService, KNOWN_EXPERIMENT_IDS

    exp_id = args.experiment_id.upper().strip()
    if exp_id not in KNOWN_EXPERIMENT_IDS:
        print(f"ERROR: unknown experiment '{exp_id}'. "
              f"Known: {', '.join(KNOWN_EXPERIMENT_IDS)}")
        return 2
    config = json.loads(args.config) if args.config else {}
    service = ExperimentService()
    total = 6

    _banner(1, total, "Validating configuration")
    normalized = service.validate_experiment_config(exp_id, config)
    print(f"  OK  {json.dumps(normalized, sort_keys=True)}")

    _banner(2, total, f"Executing {exp_id}")
    started = time.perf_counter()
    result = service.run_experiment_by_id(exp_id, config=normalized)
    elapsed = time.perf_counter() - started
    print(f"  OK  status={result.get('status')} in {elapsed:.2f}s")
    print(f"  OK  result_hash={result.get('result_hash')}")

    _banner(3, total, "Evidence: canonical hashes + trust profile")
    print(f"  OK  configuration_hash={result.get('configuration_hash')}")
    for dimension in result.get("trust_profile", []):
        print(f"      - {dimension['label']}: {dimension['status']}")

    _banner(4, total, "Verifying evidence envelope")
    assert len(result.get("result_hash", "")) == 64, "result hash malformed"
    assert len(result.get("configuration_hash", "")) == 64, "config hash malformed"
    print("  OK  canonical SHA-256 hashes well-formed")

    _banner(5, total, "Exporting reproducibility package")
    if args.package:
        from backend.app.research.reproducibility import export_reproducibility_package
        package = export_reproducibility_package(exp_id, result, normalized)
        print(f"  OK  {package['package_path']}")
        print(f"  OK  package_hash={package['package_hash']} "
              f"({len(package['files'])} files)")
    else:
        print("  SKIP (--package not passed)")

    _banner(6, total, "Report")
    out_file = None
    from backend.app.services.experiment_service import EXPERIMENT_RESULT_FILES, RESULTS_DIR
    out_file = RESULTS_DIR / EXPERIMENT_RESULT_FILES[exp_id]
    print(f"  OK  results persisted to {out_file}")
    print(f"\nDONE {exp_id} elapsed={elapsed:.2f}s hash={result.get('result_hash')}")
    return 0


def cmd_benchmark_run(args: argparse.Namespace) -> int:
    from backend.app.research import benchmark

    print("Running standardized SentinelCrypt benchmark protocol …")
    report = benchmark.run_benchmark(
        n_samples=args.samples, seed=args.seed, repeats=args.repeats,
    )
    print(f"  OK  benchmark_id={report['benchmark_id']}")
    print(f"  OK  report_hash={report['report_hash']}")
    for metric, stats in report["summary"].items():
        print(f"      {metric}: {stats}")
    print("  OK  report written to results/reports/benchmark_latest.md")
    return 0


def cmd_challenge_run(args: argparse.Namespace) -> int:
    from backend.app.research.challenges import run_preset

    print(f"Running research challenge preset {args.preset} …")
    result = run_preset(args.preset, n_runs=args.runs)
    analysis = result.get("analysis", {})
    print(f"  OK  challenge_id={result['challenge_id']}")
    print(f"  OK  evidence_hash={result['evidence_hash']}")
    print(f"  OK  status={result['status']}")
    if "metric_stats" in analysis:
        for metric, stats in list(analysis["metric_stats"].items())[:5]:
            print(f"      {metric}: mean={stats.get('mean')} ci95=[{stats.get('ci95_low')}, {stats.get('ci95_high')}]")
    if "determinism_classification" in analysis:
        print(f"      determinism: {analysis['determinism_classification']}")
    print(f"  OK  persisted to {result.get('persisted_to')}")
    return 0


def cmd_verify_artifact(args: argparse.Namespace) -> int:
    from backend.app.cryptography import notary

    path = Path(args.artifact)
    if not path.exists():
        print(f"ERROR: artifact not found: {path}")
        return 2
    with open(path, "r", encoding="utf-8") as f:
        artifact = json.load(f)
    report = notary.verify_artifact(artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


def cmd_list(args: argparse.Namespace) -> int:
    from backend.app.services.experiment_service import ExperimentService, KNOWN_EXPERIMENT_IDS
    from backend.app.research.challenges import QUESTION_PRESETS

    service = ExperimentService()
    print("Experiments:")
    for exp in service.list_experiments():
        print(f"  {exp['experiment_id']:<8} {exp.get('status', 'READY_TO_RUN'):<15} {exp.get('title', '')}")
    print("\nChallenge presets:")
    for preset in QUESTION_PRESETS:
        print(f"  {preset['id']:<4} [{preset['kind']:<15}] {preset['question']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sentinel",
        description="SentinelCrypt AI research workflow CLI",
    )
    sub = parser.add_subparsers(dest="command")

    exp = sub.add_parser("experiment", help="Experiment operations")
    exp_sub = exp.add_subparsers(dest="subcommand")
    exp_run = exp_sub.add_parser("run", help="Run one experiment end-to-end")
    exp_run.add_argument("experiment_id", help="e.g. EXP-B")
    exp_run.add_argument("--config", default=None, help="JSON configuration object")
    exp_run.add_argument("--package", action="store_true",
                         help="Also export the full reproducibility package")
    exp_run.set_defaults(func=cmd_experiment_run)

    bench = sub.add_parser("benchmark", help="Benchmark operations")
    bench_sub = bench.add_subparsers(dest="subcommand")
    bench_run = bench_sub.add_parser("run", help="Run the standardized benchmark")
    bench_run.add_argument("--samples", type=int, default=1200)
    bench_run.add_argument("--seed", type=int, default=42)
    bench_run.add_argument("--repeats", type=int, default=2)
    bench_run.set_defaults(func=cmd_benchmark_run)

    chal = sub.add_parser("challenge", help="Research challenge operations")
    chal_sub = chal.add_subparsers(dest="subcommand")
    chal_run = chal_sub.add_parser("run", help="Run a Q1–Q5 preset challenge")
    chal_run.add_argument("--preset", required=True, help="Q1..Q5")
    chal_run.add_argument("--runs", type=int, default=None)
    chal_run.set_defaults(func=cmd_challenge_run)

    verify = sub.add_parser("verify-artifact", help="Verify a signed research artifact")
    verify.add_argument("artifact", help="Path to artifact JSON")
    verify.set_defaults(func=cmd_verify_artifact)

    listing = sub.add_parser("list", help="List experiments and challenge presets")
    listing.set_defaults(func=cmd_list)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
