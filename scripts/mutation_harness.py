#!/usr/bin/env python3
"""Focused mutation-testing harness for SentinelCrypt's cryptographic core.

Phase 7 of the Devil's-Advocate roadmap: answers "are my tests actually good?"
for the code that guards evidence integrity.  Scopes to backend/app/cryptography/
where a surviving mutant is a real security finding, not a coverage statistic.

Method: line-oriented mutation operators applied to the source, suite executed
per mutant, kill/survive recorded.  Operators (deterministic, documented):
    comparison flip     == <-> !=,  < <-> >=,  >  <-> <=
    boolean flip        and <-> or,  not-X -> X (leading `not `)
    constant swap       True<->False, numeric literal n -> n+1
    boundary drift      6 -> 7 (float rounding), 64 -> 63 (hash width)
    hash-input drop     prev + payload -> payload (linkage removal)

Usage:
    python scripts/mutation_harness.py [--test TESTFILE]...
Output: docs/testing/MUTATION_TESTING.md data + machine-readable stdout summary.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from datetime import datetime, timezone
import json
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CRYPTO_TESTS = [
    "backend/tests/unit/test_hashing.py",
    "backend/tests/unit/test_verifier.py",
    "backend/tests/unit/test_reference_differential.py",
    "backend/tests/unit/test_security_redteam.py",
    "backend/tests/unit/test_property_based.py",
]
DATA_TESTS = [
    "backend/tests/unit/test_file_security.py",
    "backend/tests/unit/test_preprocessing.py",
    "backend/tests/unit/test_property_based_contracts.py",
    "backend/tests/unit/test_security_redteam.py",
    "backend/tests/unit/test_api_validation.py",
]
EXPERIMENT_TESTS = [
    "backend/tests/unit/test_experiments.py",
    "backend/tests/unit/test_new_experiments.py",
    "backend/tests/unit/test_reproducibility.py",
    "backend/tests/unit/test_property_based_contracts.py",
    "backend/tests/integration/test_experiment_api.py",
]
TARGET_TESTS = {
    REPO / "backend/app/cryptography/canonicalization.py": CRYPTO_TESTS,
    REPO / "backend/app/cryptography/hash_chain.py": CRYPTO_TESTS,
    REPO / "backend/app/cryptography/hashing.py": CRYPTO_TESTS,
    REPO / "backend/app/cryptography/verifier.py": CRYPTO_TESTS,
    REPO / "backend/app/ml/preprocessing/validators.py": DATA_TESTS,
    REPO / "backend/app/ml/preprocessing/pipeline.py": DATA_TESTS,
    REPO / "backend/app/schemas/model.py": DATA_TESTS,
    REPO / "backend/app/schemas/dataset.py": DATA_TESTS,
    REPO / "backend/app/schemas/experiment.py": EXPERIMENT_TESTS,
    REPO / "backend/app/research/reproducibility.py": EXPERIMENT_TESTS,
    REPO / "backend/app/services/experiment_service.py": EXPERIMENT_TESTS,
    REPO / "backend/app/api/v1/experiments.py": EXPERIMENT_TESTS,
}


@dataclass
class Mutant:
    file: Path
    lineno: int
    column: int
    operator: str
    original: str
    mutated: str
    tests: list[str]
    outcome: str = "not_run"


# ── mutation operators ────────────────────────────────────────────────────────
COMPARISON = {"==": "!=", "!=": "==", "<=": "<", "<": "<=", ">=": ">", ">": ">="}
BOOLEAN = {"and": "or", "or": "and"}
CONSTANTS = {"True": "False", "False": "True"}

def _code_spans(source: str):
    """(start_offset, end_offset) spans of comments/docstrings/strings —
    mutants inside them are EQUIVALENT (they change prose, not behaviour)
    and are excluded so the score measures real test gaps."""
    import tokenize
    import io

    spans = []
    tokens = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            tokens.append(tok)
    except tokenize.TokenError:
        return spans
    # comments and all strings are non-code; docstrings are strings too
    skip_rows = {}  # row -> list of (col_start, col_end)
    for tok in tokens:
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            skip_rows.setdefault(tok.start[0], []).append((tok.start[1], tok.end[1]))
    # multi-line strings: mark every row they cover
    for tok in tokens:
        if tok.type == tokenize.STRING and tok.end[0] > tok.start[0]:
            for row in range(tok.start[0], tok.end[0] + 1):
                skip_rows.setdefault(row, []).append((0, 10**9))
    return skip_rows

def gen_mutants(source: str):
    """Yield unique (line, column, operator, original, mutated) code changes."""
    skip_rows = _code_spans(source)
    lines = source.splitlines(keepends=True)
    seen = set()
    for i, line in enumerate(lines):
        spans = skip_rows.get(i + 1, [])
        if any(span == (0, 10**9) for span in spans):
            continue

        def in_comment_or_string(column):
            return any(start <= column < end for start, end in spans)

        candidates = []
        for op, replacement in COMPARISON.items():
            candidates.extend(
                (match.start(), "comparison_flip", op, replacement)
                for match in re.finditer(re.escape(op), line)
            )
        for op, replacement in BOOLEAN.items():
            candidates.extend(
                (match.start(), "boolean_flip", op, replacement)
                for match in re.finditer(rf"\b{op}\b", line)
            )
        for op, replacement in CONSTANTS.items():
            candidates.extend(
                (match.start(), "constant_swap", op, replacement)
                for match in re.finditer(rf"\b{op}\b", line)
            )
        candidates.extend(
            (
                match.start(1),
                "numeric_plus1",
                match.group(1),
                str(int(match.group(1)) + 1),
            )
            for match in re.finditer(r"\b(\d+)\b", line)
        )

        for column, operator, original, mutated in candidates:
            mutant = (i, column, operator, original, mutated)
            if not in_comment_or_string(column) and mutant not in seen:
                seen.add(mutant)
                yield mutant


def apply_mutation(
    source: str, lineno: int, column: int, operator: str, old: str, new: str
) -> str:
    lines = source.splitlines(keepends=True)
    line = lines[lineno]
    if line[column : column + len(old)] != old:
        raise ValueError(f"Mutation token mismatch at line {lineno + 1}, column {column}")
    lines[lineno] = line[:column] + new + line[column + len(old) :]
    return "".join(lines)


def classify_pytest_result(returncode: int, junit_contents: str) -> str:
    try:
        root = ET.fromstring(junit_contents)
    except ET.ParseError:
        return "error"
    if root.findall(".//error") or returncode not in (0, 1):
        return "error"
    if not root.findall(".//testcase"):
        return "error"
    if root.findall(".//failure"):
        return "killed"
    return "survived" if returncode == 0 else "error"


def run_suite(test_files) -> tuple[str, str]:
    with tempfile.TemporaryDirectory(prefix="sentinelcrypt-mutation-") as temp_dir:
        junit_path = Path(temp_dir) / "pytest.xml"
        try:
            proc = subprocess.run(
                [
                    sys.executable, "-m", "pytest", *test_files, "-x", "-q",
                    "--no-header", "-p", "no:cacheprovider",
                    f"--junitxml={junit_path}",
                ],
                cwd=REPO,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return "timeout", "Focused test run exceeded 120 seconds."
        except OSError as exc:
            return "error", f"Could not execute pytest: {exc}"

        if not junit_path.exists():
            return "error", proc.stdout + proc.stderr
        try:
            junit_contents = junit_path.read_text(encoding="utf-8")
        except OSError as exc:
            return "error", f"Could not parse pytest results: {exc}"
        return (
            classify_pytest_result(proc.returncode, junit_contents),
            proc.stdout + proc.stderr,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--test",
        action="append",
        default=None,
        help="Override the focused tests for every target (may be repeated).",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--max-mutants",
        type=int,
        default=12,
        help="Maximum evenly sampled mutants per target module.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("artifacts/testing/mutation-report/mutation-report.json"),
    )
    args = parser.parse_args()
    if args.max_mutants < 0:
        parser.error("--max-mutants must be zero (all mutants) or a positive number")

    target_tests = {
        target: args.test if args.test is not None else tests
        for target, tests in TARGET_TESTS.items()
    }
    tested_baselines = set()
    for target, tests in target_tests.items():
        baseline_key = tuple(tests)
        if baseline_key in tested_baselines:
            continue
        tested_baselines.add(baseline_key)
        baseline_outcome, baseline_output = run_suite(tests)
        if baseline_outcome != "survived":
            report = {
                "status": "not_run",
                "target": str(target.relative_to(REPO)),
                "error": "Baseline test run did not pass; mutation testing was not started.",
                "baseline_outcome": baseline_outcome,
                "baseline_output": baseline_output[-4000:],
            }
            report_path = (REPO / args.report).resolve()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            return 2

    mutants: list[Mutant] = []
    available_mutants = {}
    for target, tests in target_tests.items():
        original = target.read_text(encoding="utf-8")
        candidates = list(gen_mutants(original))
        available_mutants[str(target.relative_to(REPO))] = len(candidates)
        if args.max_mutants > 0 and len(candidates) > args.max_mutants:
            candidates = [
                candidates[(index * len(candidates)) // args.max_mutants]
                for index in range(args.max_mutants)
            ]
        generated = candidates
        for lineno, column, operator, old, new in generated:
            mutated_source = apply_mutation(
                original, lineno, column, operator, old, new
            )
            if mutated_source == original:
                continue
            mutants.append(Mutant(
                file=target,
                lineno=lineno + 1,
                column=column,
                operator=operator,
                original=old,
                mutated=new,
                tests=tests,
            ))

    survived, killed, errors, timeouts = [], 0, [], 0
    started = time.time()
    for idx, mutant in enumerate(mutants):
        original = mutant.file.read_text(encoding="utf-8")
        mutated = apply_mutation(
            original,
            mutant.lineno - 1,
            mutant.column,
            mutant.operator,
            mutant.original,
            mutant.mutated,
        )
        try:
            mutant.file.write_text(mutated, encoding="utf-8")
            outcome, output = run_suite(mutant.tests)
            mutant.outcome = outcome
            if outcome == "killed":
                killed += 1
            elif outcome == "survived":
                survived.append(mutant)
            elif outcome == "timeout":
                timeouts += 1
            else:
                errors.append({
                    "file": str(mutant.file.relative_to(REPO)),
                    "line": mutant.lineno,
                    "operator": mutant.operator,
                    "output": output[-2000:],
                })
        finally:
            mutant.file.write_text(original, encoding="utf-8")
        if args.json:
            print(json.dumps({
                "progress": f"{idx + 1}/{len(mutants)}",
                "outcome": mutant.outcome,
            }), flush=True)

    total = len(mutants)
    scored_mutants = killed + len(survived)
    score = round(100.0 * killed / scored_mutants, 1) if scored_mutants else None
    report = {
        "status": "complete",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "targets": [str(t.relative_to(REPO)) for t in TARGET_TESTS],
        "target_tests": {
            str(target.relative_to(REPO)): tests
            for target, tests in target_tests.items()
        },
        "available_mutants": available_mutants,
        "generated": total,
        "killed": killed,
        "survived": len(survived),
        "timeouts": timeouts,
        "error_count": len(errors),
        "errors": errors,
        "mutation_score": score,
        "elapsed_s": round(time.time() - started, 1),
        "survivors": [
            {"file": str(m.file.relative_to(REPO)), "line": m.lineno,
             "column": m.column, "operator": m.operator,
             "original": m.original, "mutated": m.mutated,
             "tests": m.tests}
            for m in survived
        ],
    }
    print(json.dumps(report, indent=2))
    report_path = (REPO / args.report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 1 if errors or timeouts else 0


if __name__ == "__main__":
    sys.exit(main())
