"""Automated pytest suite for SentinelCrypt Metamorphic Relations.

Verifies valid metamorphic invariants across:
1. Preprocessing (Metadata dropping, key ordering, out-of-vocabulary fallback, batch isolation)
2. Canonicalization (Key permutation, whitespace normalization, UTC timezone normalization, non-finite float rejection)
3. Cryptographic Hashing (Avalanche sensitivity, operand non-commutativity, Merkle domain separation, odd-leaf duplication)
4. Evidence Verification (Inductive extension, tamper sensitivity, prefix validity, suffix rejection, notary entanglement)
5. Prediction Behavior (Metadata invariance, key order invariance, positive weight monotonicity, batch row isolation, threshold monotonicity)
6. Explanation Behavior (Null player axiom, efficiency completeness, linear attribution shift, stability noise monotonicity, explanation metadata invariance)
"""
from __future__ import annotations

import pytest

from backend.tests.metamorphic.framework import Category
from backend.tests.metamorphic.registry import ALL_RELATIONS, build_harness


@pytest.mark.parametrize(
    "relation",
    ALL_RELATIONS,
    ids=lambda r: f"{r.id}:{r.name.replace(' ', '_')}",
)
def test_all_metamorphic_relations(relation):
    """Parametrized automated test running every registered Metamorphic Relation."""
    result = relation.execute()
    assert result.passed, (
        f"Metamorphic Relation [{result.relation_id}] '{result.name}' FAILED!\n"
        f"Category: {result.category}\n"
        f"Message: {result.message}\n"
        f"Details: {result.details}\n"
        f"Error: {result.error}"
    )


class TestMetamorphicHarnessInfrastructure:
    """Test suite for the metamorphic harness execution engine and reporting."""

    def test_harness_run_all(self):
        harness = build_harness()
        report = harness.run_all()
        assert report.total_relations == len(ALL_RELATIONS)
        assert report.passed_count == len(ALL_RELATIONS)
        assert report.failed_count == 0
        assert report.pass_rate == 100.0

    def test_harness_category_filter(self):
        harness = build_harness()
        for cat in Category:
            report = harness.run_all(category_filter=cat.value)
            assert report.total_relations > 0
            assert report.failed_count == 0
            for r in report.results:
                assert r.category == cat.value

    def test_harness_report_serialization(self):
        harness = build_harness()
        report = harness.run_all(category_filter=Category.CANONICALIZATION.value)
        json_str = report.to_json()
        assert "pass_rate_percent" in json_str
        assert "MR-CAN-01" in json_str
