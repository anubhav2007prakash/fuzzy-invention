"""Differential Testing Framework for SentinelCrypt AI.

Provides DifferentialTest dataclass, DifferentialHarness executor, and
DifferentialSuiteReport result container.  All differential test modules in
this package return DifferentialResult objects that are aggregated by the
harness and surfaced in a structured JSON-serialisable report.

Design Principles
-----------------
1. **Two independent implementations**: production code vs. deliberately simple
   reference code.  Both must be derived from the same specification but MUST
   NOT share implementation.
2. **Deterministic inputs**: tests use fixed seeds so failures are reproducible.
3. **Fail loudly**: any mismatch raises AssertionError with a full diff.
4. **Component isolation**: each component (hashing, canonicalization, chain,
   verification, metrics, preprocessing) is tested in a separate module.
"""
from __future__ import annotations

import dataclasses
import json
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Sequence


# ── Result types ──────────────────────────────────────────────────────────────

@dataclasses.dataclass
class DifferentialResult:
    """Outcome of a single differential comparison."""
    test_id: str
    description: str
    component: str
    passed: bool
    production_output: Any
    reference_output: Any
    mismatch_detail: Optional[str]  # None when passed
    duration_ms: float
    case_label: str = ""            # e.g. "seed=42 n=100"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "description": self.description,
            "component": self.component,
            "case_label": self.case_label,
            "passed": self.passed,
            "mismatch_detail": self.mismatch_detail,
            "duration_ms": round(self.duration_ms, 3),
        }

    def assert_pass(self) -> None:
        if not self.passed:
            raise AssertionError(
                f"\n[DIFFERENTIAL FAILURE] {self.test_id}\n"
                f"  Component  : {self.component}\n"
                f"  Case       : {self.case_label}\n"
                f"  Description: {self.description}\n"
                f"  Detail     : {self.mismatch_detail}\n"
                f"  Production : {_truncate(self.production_output)}\n"
                f"  Reference  : {_truncate(self.reference_output)}\n"
            )


@dataclasses.dataclass
class DifferentialSuiteReport:
    """Aggregated result across all differential tests."""
    results: List[DifferentialResult]
    total: int
    passed: int
    failed: int
    duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "pass_rate": round(self.passed / self.total, 4) if self.total else 1.0,
                "duration_ms": round(self.duration_ms, 2),
            },
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def assert_all_pass(self) -> None:
        failures = [r for r in self.results if not r.passed]
        if failures:
            msgs = "\n".join(
                f"  • [{r.test_id}] {r.description}: {r.mismatch_detail}"
                for r in failures
            )
            raise AssertionError(
                f"\n{len(failures)} differential test(s) FAILED:\n{msgs}\n"
            )


# ── Harness ───────────────────────────────────────────────────────────────────

class DifferentialHarness:
    """Collect and run differential test functions.

    Usage::

        harness = DifferentialHarness()

        @harness.register("DT-HASH-01", "SHA-256 string hashing", "hashing")
        def _test_hash_string(h):
            ...
            yield h.compare(prod_val, ref_val, case_label="hello-world")

        report = harness.run()
        report.assert_all_pass()
    """

    def __init__(self) -> None:
        self._tests: List[_TestEntry] = []

    def register(
        self,
        test_id: str,
        description: str,
        component: str,
    ) -> Callable:
        """Decorator that registers a generator function as a differential test."""
        def decorator(fn: Callable) -> Callable:
            self._tests.append(_TestEntry(test_id, description, component, fn))
            return fn
        return decorator

    def run(self, filter_component: Optional[str] = None) -> DifferentialSuiteReport:
        """Execute all registered tests and return a report."""
        suite_start = time.perf_counter()
        results: List[DifferentialResult] = []

        for entry in self._tests:
            if filter_component and entry.component != filter_component:
                continue
            t0 = time.perf_counter()
            try:
                helper = _RunHelper(entry.test_id, entry.description, entry.component)
                # Generator tests yield DifferentialResult objects
                gen = entry.fn(helper)
                if gen is not None:
                    for result in gen:
                        results.append(result)
                else:
                    # Non-generator: helper accumulates results internally
                    results.extend(helper._results)
            except Exception:
                elapsed = (time.perf_counter() - t0) * 1000.0
                results.append(DifferentialResult(
                    test_id=entry.test_id,
                    description=entry.description,
                    component=entry.component,
                    passed=False,
                    production_output=None,
                    reference_output=None,
                    mismatch_detail=f"EXCEPTION during test:\n{traceback.format_exc()}",
                    duration_ms=elapsed,
                ))

        total_ms = (time.perf_counter() - suite_start) * 1000.0
        passed = sum(1 for r in results if r.passed)
        return DifferentialSuiteReport(
            results=results,
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            duration_ms=total_ms,
        )


@dataclasses.dataclass
class _TestEntry:
    test_id: str
    description: str
    component: str
    fn: Callable


class _RunHelper:
    """Passed into test functions to create DifferentialResult objects."""

    def __init__(self, test_id: str, description: str, component: str) -> None:
        self._test_id = test_id
        self._description = description
        self._component = component
        self._results: List[DifferentialResult] = []

    def compare(
        self,
        production: Any,
        reference: Any,
        *,
        case_label: str = "",
        comparator: Optional[Callable[[Any, Any], bool]] = None,
    ) -> DifferentialResult:
        """Compare production output to reference output; return a result."""
        t0 = time.perf_counter()
        if comparator is not None:
            match = comparator(production, reference)
        else:
            match = production == reference

        detail = None if match else _build_diff(production, reference)
        result = DifferentialResult(
            test_id=self._test_id,
            description=self._description,
            component=self._component,
            passed=match,
            production_output=production,
            reference_output=reference,
            mismatch_detail=detail,
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            case_label=case_label,
        )
        self._results.append(result)
        return result


# ── Utilities ─────────────────────────────────────────────────────────────────

def _truncate(value: Any, max_len: int = 300) -> str:
    s = repr(value)
    return s if len(s) <= max_len else s[:max_len] + "…"


def _build_diff(production: Any, reference: Any) -> str:
    """Build a human-readable diff string."""
    prod_str = _truncate(production, 500)
    ref_str = _truncate(reference, 500)
    if isinstance(production, str) and isinstance(reference, str):
        # Character-level hint for short strings
        first_diff = next(
            (i for i, (a, b) in enumerate(zip(production, reference)) if a != b),
            min(len(production), len(reference))
        )
        return (
            f"Strings differ at byte {first_diff}.\n"
            f"  prod[{first_diff}:+10]={production[first_diff:first_diff+10]!r}\n"
            f"  ref [{first_diff}:+10]={reference[first_diff:first_diff+10]!r}"
        )
    return f"Production:\n  {prod_str}\nReference:\n  {ref_str}"
