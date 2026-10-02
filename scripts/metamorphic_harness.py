#!/usr/bin/env python3
"""Metamorphic Testing CLI Harness for SentinelCrypt AI.

Executes and verifies metamorphic relations across all six core areas:
- Feature Preprocessing
- RFC 8785 Canonicalization
- Cryptographic Hashing
- Evidence Verification & Notary
- Prediction Behavior
- Explainable AI (SHAP & Stability)

Usage:
    python scripts/metamorphic_harness.py
    python scripts/metamorphic_harness.py --category preprocessing
    python scripts/metamorphic_harness.py --json
    python scripts/metamorphic_harness.py --list
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.tests.metamorphic.framework import Category
from backend.tests.metamorphic.registry import ALL_RELATIONS, build_harness


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SentinelCrypt AI Metamorphic Testing Harness"
    )
    parser.add_argument(
        "-c",
        "--category",
        choices=[c.value for c in Category] + ["all"],
        default="all",
        help="Filter execution to a specific metamorphic relation category.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON report to stdout.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=REPO_ROOT / "results" / "metamorphic-report.json",
        help="Path to save output JSON report.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed rationale and execution metadata for each relation.",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List all registered metamorphic relations without executing.",
    )
    return parser.parse_args()


def print_relation_catalog() -> None:
    print("\n" + "=" * 90)
    print(" SentinelCrypt AI — Registered Metamorphic Relations Catalog")
    print("=" * 90)
    for rel in ALL_RELATIONS:
        print(f"\n[{rel.id}] {rel.name}")
        print(f"  Category    : {rel.category.value}")
        print(f"  Rationale   : {rel.rationale}")
        print(f"  Transform   : {rel.input_transformation}")
        print(f"  Property    : {rel.expected_property}")
        print(f"  Limitations : {rel.limitations}")
    print("\nTotal Registered Relations: ", len(ALL_RELATIONS))


def run_harness(args: argparse.Namespace) -> int:
    harness = build_harness()
    cat_filter = None if args.category == "all" else args.category

    if not args.json:
        print("\n" + "=" * 80)
        print(" SentinelCrypt AI — Metamorphic Testing Suite")
        print(f" Category Filter: {args.category.upper()}")
        print(f" Registered Relations: {len(ALL_RELATIONS)}")
        print("=" * 80 + "\n")

    report = harness.run_all(category_filter=cat_filter)

    if args.json:
        print(report.to_json())
    else:
        # Formatted console output
        header = f"{'ID':<12} | {'Category':<22} | {'Relation Name':<30} | {'Status':<6} | {'Time (ms)':<9}"
        print(header)
        print("-" * len(header))

        for res in report.results:
            status_str = "PASS" if res.passed else "FAIL"
            name_trunc = res.name if len(res.name) <= 30 else res.name[:27] + "..."
            print(
                f"{res.relation_id:<12} | {res.category:<22} | {name_trunc:<30} | {status_str:<6} | {res.duration_ms:<9.2f}"
            )
            if args.verbose or not res.passed:
                print(f"   -> Message : {res.message}")
                if res.details:
                    print(f"   -> Details : {res.details}")
                if res.error:
                    print(f"   -> Error   : {res.error}")
                print()

        print("-" * len(header))
        print(f"Total Evaluated : {report.total_relations}")
        print(f"Passed          : {report.passed_count}")
        print(f"Failed          : {report.failed_count}")
        print(f"Pass Rate       : {report.pass_rate}%")
        print(f"Elapsed Time    : {report.duration_ms:.2f} ms")
        print("=" * 80)

    # Save to output file
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report.to_json(), encoding="utf-8")
        if not args.json:
            print(f"\n[Artifact] Report saved to: {args.output}")
    except Exception as exc:
        if not args.json:
            print(f"\n[Warning] Could not write report to {args.output}: {exc}")

    return 0 if report.failed_count == 0 else 1


def main() -> None:
    args = parse_args()
    if args.list:
        print_relation_catalog()
        sys.exit(0)

    sys.exit(run_harness(args))


if __name__ == "__main__":
    main()
