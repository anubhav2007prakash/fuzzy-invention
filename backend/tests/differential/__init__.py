"""Differential testing suite and reference implementations for SentinelCrypt AI.

Modules
-------
framework                         Core harness, DifferentialResult, DifferentialSuiteReport
test_hashing_differential         DT-HASH-01 … DT-HASH-08
test_canonicalization_differential DT-CAN-01 … DT-CAN-12
test_hash_chain_differential      DT-CHAIN-01 … DT-CHAIN-08
test_reference_canonicalization   DT-CAN-01 … DT-CAN-12
test_reference_hashing            DT-HASH-01 … DT-HASH-08
test_reference_chain              DT-CHAIN-09 … DT-CHAIN-11
test_reference_verification       DT-VER-01 … DT-VER-09
test_reference_signature          DT-SIG-01 … DT-SIG-08
test_reference_merkle             DT-MERKLE-01 … DT-MERKLE-10
test_metrics_differential         DT-METR-01 … DT-METR-08
test_preprocessing_differential   DT-PREP-01 … DT-PREP-10

Run all differential tests via::

    pytest backend/tests/differential/ -v --tb=short

Or a single component::

    pytest backend/tests/differential/test_hashing_differential.py -v
"""
from backend.tests.differential.framework import (
    DifferentialHarness,
    DifferentialResult,
    DifferentialSuiteReport,
)

__all__ = [
    "DifferentialHarness",
    "DifferentialResult",
    "DifferentialSuiteReport",
]
