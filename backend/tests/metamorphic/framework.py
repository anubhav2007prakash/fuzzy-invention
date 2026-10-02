"""Metamorphic Testing Core Framework for SentinelCrypt AI.

Defines the base abstractions, result structures, execution harness,
and reporting mechanisms for metamorphic testing across:
- Preprocessing
- Canonicalization
- Cryptographic Hashing
- Evidence Verification
- Prediction Behavior
- Explanation Behavior
"""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence


class Category(str, Enum):
    """Metamorphic testing target categories in SentinelCrypt."""

    PREPROCESSING = "preprocessing"
    CANONICALIZATION = "canonicalization"
    HASHING = "cryptographic_hashing"
    VERIFICATION = "evidence_verification"
    PREDICTION = "prediction_behavior"
    EXPLANATION = "explanation_behavior"


@dataclass
class MetamorphicResult:
    """Outcome of evaluating a single Metamorphic Relation."""

    relation_id: str
    name: str
    category: str
    passed: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MetamorphicRelation(ABC):
    """Abstract base class for a Metamorphic Relation (MR).

    Attributes:
        id: Unique identifier (e.g. 'MR-PRE-01').
        name: Concise human-readable name.
        category: The architectural subsystem under test.
        rationale: Domain/mathematical justification for why this relation must hold.
        input_transformation: Exact transformation applied to source input x -> x'.
        expected_property: Mathematical or logical relation between f(x) and f(x').
        limitations: Bounds, conditions, and assumptions under which the relation holds.
        test_implementation: Description of test mechanics and assertions.
    """

    id: str
    name: str
    category: Category
    rationale: str
    input_transformation: str
    expected_property: str
    limitations: str
    test_implementation: str

    def execute(self, **kwargs: Any) -> MetamorphicResult:
        """Run the metamorphic test and return a structured result."""
        start_time = time.perf_counter()
        try:
            passed, message, details = self.evaluate(**kwargs)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return MetamorphicResult(
                relation_id=self.id,
                name=self.name,
                category=self.category.value,
                passed=passed,
                message=message,
                details=details,
                duration_ms=round(duration_ms, 2),
                error=None,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return MetamorphicResult(
                relation_id=self.id,
                name=self.name,
                category=self.category.value,
                passed=False,
                message=f"Evaluation failed with exception: {exc}",
                details={"exception_type": type(exc).__name__},
                duration_ms=round(duration_ms, 2),
                error=str(exc),
            )

    @abstractmethod
    def evaluate(self, **kwargs: Any) -> tuple[bool, str, Dict[str, Any]]:
        """Evaluate the metamorphic relation.

        Returns:
            (passed: bool, message: str, details: Dict[str, Any])
        """
        raise NotImplementedError


@dataclass
class MetamorphicSuiteReport:
    """Summary report of an entire metamorphic test suite run."""

    total_relations: int
    passed_count: int
    failed_count: int
    categories: Dict[str, Dict[str, int]]
    duration_ms: float
    results: List[MetamorphicResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.total_relations == 0:
            return 100.0
        return round((self.passed_count / self.total_relations) * 100.0, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_relations": self.total_relations,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "pass_rate_percent": self.pass_rate,
            "duration_ms": round(self.duration_ms, 2),
            "categories": self.categories,
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class MetamorphicHarness:
    """Execution harness that manages and executes Metamorphic Relations."""

    def __init__(self) -> None:
        self._relations: List[MetamorphicRelation] = []

    def register(self, relation: MetamorphicRelation) -> None:
        """Register a single metamorphic relation."""
        self._relations.append(relation)

    def register_many(self, relations: Sequence[MetamorphicRelation]) -> None:
        """Register multiple metamorphic relations."""
        for rel in relations:
            self.register(rel)

    @property
    def relations(self) -> List[MetamorphicRelation]:
        return list(self._relations)

    def run_all(self, category_filter: Optional[str] = None, **kwargs: Any) -> MetamorphicSuiteReport:
        """Run all registered relations, optionally filtered by category name."""
        start_time = time.perf_counter()
        results: List[MetamorphicResult] = []
        category_stats: Dict[str, Dict[str, int]] = {}

        for rel in self._relations:
            if category_filter and rel.category.value != category_filter:
                continue

            cat_key = rel.category.value
            if cat_key not in category_stats:
                category_stats[cat_key] = {"total": 0, "passed": 0, "failed": 0}

            category_stats[cat_key]["total"] += 1
            res = rel.execute(**kwargs)
            results.append(res)

            if res.passed:
                category_stats[cat_key]["passed"] += 1
            else:
                category_stats[cat_key]["failed"] += 1

        total_ms = (time.perf_counter() - start_time) * 1000.0
        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed)

        return MetamorphicSuiteReport(
            total_relations=len(results),
            passed_count=passed,
            failed_count=failed,
            categories=category_stats,
            duration_ms=total_ms,
            results=results,
        )
