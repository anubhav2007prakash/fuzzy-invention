"""Verification helpers and invariant assertions for failure injection tests.

Every controlled failure test verifies that SentinelCrypt:
1. Fails safely (typed errors, safe HTTP status codes, no silent crashes).
2. Reports meaningful errors (clear diagnostics, actionable messages).
3. Does not silently produce invalid research results (no fake outputs/metrics).
4. Does not corrupt existing evidence (hash chains and records remain pristine).
5. Maintains consistent state (relational consistency, no orphan rows).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Type

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.app.core.exceptions import SentinelCryptException
from backend.app.cryptography.verifier import verify_ledger
from backend.app.research.db_integrity import audit_database


@dataclass
class FailureVerificationRecord:
    scenario_name: str
    fails_safely: bool = False
    reports_meaningful_error: bool = False
    no_silent_invalid_results: bool = False
    evidence_not_corrupted: bool = False
    maintains_consistent_state: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return (
            self.fails_safely
            and self.reports_meaningful_error
            and self.no_silent_invalid_results
            and self.evidence_not_corrupted
            and self.maintains_consistent_state
        )


class FailureVerificationReport:
    """Aggregates and formats verification outcomes across all failure injection runs."""

    def __init__(self) -> None:
        self.records: List[FailureVerificationRecord] = []

    def record(self, item: FailureVerificationRecord) -> None:
        self.records.append(item)

    @property
    def total_count(self) -> int:
        return len(self.records)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.records if r.passed)

    @property
    def all_passed(self) -> bool:
        return self.passed_count == self.total_count and self.total_count > 0

    def generate_summary(self) -> str:
        lines = [
            "=" * 92,
            " SENTINELCRYPT CONTROLLED FAILURE INJECTION VERIFICATION REPORT",
            "=" * 92,
            f"{'Failure Scenario':<28} | {'Safe':<5} | {'Error':<6} | {'NoFake':<7} | {'EvidOK':<7} | {'StateOK':<8} | {'Status'}",
            "-" * 92,
        ]
        for r in self.records:
            s_safe = "PASS" if r.fails_safely else "FAIL"
            s_err = "PASS" if r.reports_meaningful_error else "FAIL"
            s_nofake = "PASS" if r.no_silent_invalid_results else "FAIL"
            s_evid = "PASS" if r.evidence_not_corrupted else "FAIL"
            s_state = "PASS" if r.maintains_consistent_state else "FAIL"
            s_overall = "PASS" if r.passed else "FAIL"
            lines.append(
                f"{r.scenario_name:<28} | {s_safe:<5} | {s_err:<6} | {s_nofake:<7} | {s_evid:<7} | {s_state:<8} | {s_overall}"
            )
        lines.append("=" * 92)
        lines.append(f"Result: {self.passed_count}/{self.total_count} failure scenarios verified successfully.")
        lines.append("=" * 92)
        return "\n".join(lines)


# ── Invariant Assertions ──────────────────────────────────────────────────────

def assert_fails_safely(
    target: Any,
    allowed_exceptions: Optional[tuple[Type[Exception], ...]] = None,
) -> Exception | Dict[str, Any]:
    """Verify that execution failed safely.

    Accepts:
      - A caught Exception: asserts it is a recognized safe exception type.
      - A callable: invokes it and asserts it raises an allowed safe exception.
      - A TestClient response (or status_code object): asserts status is an error
        status and the JSON body contains a structured error or useful detail.
    """
    default_allowed = (
        SentinelCryptException,
        ValueError,
        FileNotFoundError,
        KeyError,
        TypeError,
        RuntimeError,
        ImportError,
        OperationalError,
    )
    expected_types = allowed_exceptions or default_allowed

    # Case 1: Callable
    if callable(target):
        try:
            target()
        except expected_types as exc:
            return exc
        except Exception as exc:
            raise AssertionError(
                f"Unexpected exception {type(exc).__name__}; expected one of "
                f"{expected_types}."
            ) from exc
        raise AssertionError(
            "Operation succeeded unexpectedly — expected a safe failure."
        )

    # Case 2: Caught Exception
    if isinstance(target, Exception):
        assert isinstance(target, expected_types), (
            f"Exception {type(target).__name__} is not an allowed safe exception type {expected_types}."
        )
        return target

    # Case 3: HTTP Response
    if hasattr(target, "status_code"):
        status = target.status_code
        assert 400 <= status < 600, (
            f"Unexpected successful HTTP status {status} during controlled failure."
        )
        body = target.json()
        error = body.get("error") if isinstance(body, dict) else None
        detail = body.get("detail") if isinstance(body, dict) else None
        structured_error = isinstance(error, dict) and bool(
            error.get("code") or error.get("message")
        )
        useful_detail = (
            bool(detail.strip())
            if isinstance(detail, str)
            else detail not in (None, [], {})
        )
        assert structured_error or useful_detail, (
            f"Response has no structured error or non-empty detail: {body}"
        )
        return body

    raise TypeError(f"Unsupported target type for assert_fails_safely: {type(target)}")


def assert_meaningful_error(
    error_or_response: Any,
    expected_keywords: List[str] | str,
) -> None:
    """Verify that the error contains meaningful, descriptive diagnostic information."""
    keywords = [expected_keywords] if isinstance(expected_keywords, str) else expected_keywords

    if isinstance(error_or_response, Exception):
        msg = str(error_or_response).lower()
        if hasattr(error_or_response, "message"):
            msg += " " + str(error_or_response.message).lower()
    elif isinstance(error_or_response, dict):
        err_obj = error_or_response.get("error", error_or_response)
        msg = json.dumps(err_obj).lower()
    elif hasattr(error_or_response, "json"):
        msg = json.dumps(error_or_response.json()).lower()
    else:
        msg = str(error_or_response).lower()

    matched = [kw for kw in keywords if kw.lower() in msg]
    assert matched, (
        f"Error diagnostic '{msg}' did not contain any expected keywords: {keywords}"
    )


def assert_no_silent_invalid_results(
    outcome: Any,
    forbidden_defaults: Optional[List[Any]] = None,
) -> None:
    """Verify that the failure did not silently output synthetic or invalid research results.

    Accepts:
      - None or Exception: indicates no output was silently generated (valid).
      - Dict / Response: checks that it is NOT marked as successful or COMPLETED with fake metrics.
    """
    if outcome is None or isinstance(outcome, Exception):
        return

    if hasattr(outcome, "status_code"):
        assert_fails_safely(outcome)
        return

    if isinstance(outcome, dict):
        status = str(outcome.get("status", "")).upper()
        if status in {"COMPLETED", "SUCCESS", "SUCCEEDED", "OK", "VERIFIED"}:
            raise AssertionError(
                f"Operation silently succeeded during failure mode: {outcome}"
            )
        has_error = bool(outcome.get("error")) or bool(outcome.get("detail"))
        has_failure_status = status in {
            "FAILED", "ERROR", "ABORTED", "INCOMPLETE", "CANCELLED",
            "REJECTED", "INVALID",
        }
        assert has_error or has_failure_status, (
            f"Outcome does not explicitly report failure: {outcome}"
        )
        # Check forbidden default flags
        if forbidden_defaults:
            for forbidden in forbidden_defaults:
                assert outcome != forbidden, f"Operation silently returned forbidden default: {outcome}"
        return

    raise AssertionError(
        f"Unrecognized outcome {type(outcome).__name__}; expected an exception, "
        "None, an error response, or an explicit failure result."
    )


def assert_evidence_not_corrupted(
    records_before: List[Any],
    records_after: List[Any],
) -> None:
    """Verify that previously registered audit evidence has not been mutated or corrupted.

    Asserts:
      1. Every pre-existing record still exists with identical sequence_number and record_hash.
      2. The hash chain remains cryptographically continuous and valid over the original records.
    """
    def identity(record: Any) -> tuple[Any, Any, Any]:
        return (
            record.record_hash,
            record.previous_hash,
            record.payload_json,
        )

    before_map: Dict[Any, tuple[Any, Any, Any]] = {}
    for record in records_before:
        sequence = record.sequence_number
        assert sequence not in before_map, (
            f"Baseline ledger has duplicate sequence number {sequence}."
        )
        before_map[sequence] = identity(record)

    after_map: Dict[Any, tuple[Any, Any, Any]] = {}
    for record in records_after:
        sequence = record.sequence_number
        assert sequence not in after_map, (
            f"Post-failure ledger has duplicate sequence number {sequence}."
        )
        after_map[sequence] = identity(record)

    for sequence, before_identity in before_map.items():
        assert sequence in after_map, (
            f"Existing audit record seq={sequence} was deleted."
        )
        assert after_map[sequence] == before_identity, (
            f"Existing audit record seq={sequence} was corrupted! "
            f"Expected {before_identity!r}, found {after_map[sequence]!r}"
        )

    baseline_check = verify_ledger(records_before)
    assert baseline_check.verified, (
        f"Baseline ledger failed verification: {baseline_check.message}"
    )
    after_check = verify_ledger(records_after)
    assert after_check.verified, (
        f"Post-failure ledger failed verification: {after_check.message}"
    )


def assert_consistent_state(
    db: Session,
    expected_entity_counts: Optional[Dict[str, int]] = None,
) -> None:
    """Verify that the database is in a consistent, non-corrupted state using audit_database."""
    report = audit_database(db)
    assert report["consistent"] is True, (
        f"Database state is inconsistent after failure injection! Findings: {report['findings']}"
    )
    assert report["summary"]["errors"] == 0, (
        f"Database integrity report returned errors: {report['summary']}"
    )

    if expected_entity_counts:
        actual_counts = report["total_records_checked"]
        for key, expected_count in expected_entity_counts.items():
            assert key in actual_counts, (
                f"Unknown entity count key {key!r}; available keys: "
                f"{sorted(actual_counts)}"
            )
            assert actual_counts[key] == expected_count, (
                f"Entity count mismatch for '{key}': expected {expected_count}, got {actual_counts[key]}"
            )
