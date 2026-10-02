"""Database integrity audit — invariants over the relational store.

The hash chain detects tampering with *evidence payloads*; this module detects
the failure class the chain cannot see: relational inconsistency (orphaned
rows, dangling references, impossible timelines, duplicate identifiers).
Phases 14/15 of the Devil's-Advocate roadmap.

Every check returns findings; `audit_database` aggregates them into a report
suitable for the /research/db-integrity endpoint and scripts.  Findings have
severity ERROR (integrity violation — must investigate) or WARN (suspicious
but explainable, e.g. prediction predating its model by clock skew).
"""
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

SEVERITY_ERROR = "ERROR"
SEVERITY_WARN = "WARN"

CLOCK_SKEW_TOLERANCE_S = 5.0


def _finding(check: str, severity: str, message: str, **details) -> Dict[str, Any]:
    return {"check": check, "severity": severity, "message": message, "details": details}


def check_orphan_predictions(db: Session) -> List[Dict[str, Any]]:
    """Every prediction must reference an existing model (invariant 22.2)."""
    from backend.app.db.models import ModelRecord, Prediction

    model_ids = {row[0] for row in db.execute(select(ModelRecord.id)).all()}
    rows = db.execute(select(Prediction.id, Prediction.model_id)).all()
    return [
        _finding("orphan_prediction", SEVERITY_ERROR,
                 f"Prediction {prediction_id} references missing model {model_id}.",
                 prediction_id=prediction_id, model_id=model_id)
        for prediction_id, model_id in rows if model_id not in model_ids
    ]


def check_duplicate_audit_sequences(db: Session) -> List[Dict[str, Any]]:
    """Audit sequence numbers must be unique (DB has a UniqueConstraint, but a
    legacy/corrupted DB or raw-SQL write could violate it — verify, don't assume)."""
    from backend.app.db.models import AuditRecord

    rows = db.execute(
        select(AuditRecord.sequence_number, func.count())
        .group_by(AuditRecord.sequence_number)
        .having(func.count() > 1)
    ).all()
    return [
        _finding("duplicate_audit_sequence", SEVERITY_ERROR,
                 f"sequence_number {seq} appears {count} times.",
                 sequence_number=seq, count=count)
        for seq, count in rows
    ]


def check_audit_sequence_contiguity(db: Session) -> List[Dict[str, Any]]:
    """Sequence numbers must form 1..N without gaps (invariant 22.1's DB half)."""
    from backend.app.db.models import AuditRecord

    count = db.execute(select(func.count(AuditRecord.id))).scalar() or 0
    if count == 0:
        return []
    expected = set(range(1, count + 1))
    actual = {row[0] for row in db.execute(select(AuditRecord.sequence_number)).all()}
    missing = sorted(expected - actual)
    if missing:
        return [_finding(
            "audit_sequence_gap", SEVERITY_ERROR,
            f"Audit sequence has gaps (missing: {missing[:10]}{'…' if len(missing) > 10 else ''}) — records were deleted.",
            missing=missing,
        )]
    return []


def check_temporal_consistency(db: Session) -> List[Dict[str, Any]]:
    """Timestamps must respect causality: prediction.created_at >= model.created_at
    (a prediction cannot precede the model that made it — phase 15).  Small
    negative deltas (< 5s) are clock-skew WARNs; larger are ERRORs."""
    from backend.app.db.models import ModelRecord, Prediction

    models = dict(db.execute(select(ModelRecord.id, ModelRecord.created_at)).all())
    rows = db.execute(
        select(Prediction.id, Prediction.model_id, Prediction.created_at)
    ).all()
    findings = []
    for prediction_id, model_id, created_at in rows:
        model_created = models.get(model_id)
        if model_created is None or created_at is None:
            continue  # orphan handled elsewhere
        delta_seconds = (created_at - model_created).total_seconds()
        if delta_seconds < -CLOCK_SKEW_TOLERANCE_S:
            findings.append(_finding(
                "temporal_impossible", SEVERITY_ERROR,
                f"Prediction {prediction_id} created {abs(delta_seconds):.1f}s BEFORE its model.",
                prediction_id=prediction_id, delta_seconds=round(delta_seconds, 3),
            ))
        elif delta_seconds < 0:
            findings.append(_finding(
                "temporal_skew", SEVERITY_WARN,
                f"Prediction {prediction_id} precedes its model by {abs(delta_seconds):.2f}s (clock skew?).",
                prediction_id=prediction_id, delta_seconds=round(delta_seconds, 3),
            ))
    return findings


def check_audit_reference_integrity(db: Session) -> List[Dict[str, Any]]:
    """Every audit record's prediction_id must resolve to an existing prediction
    (invariant 22.4: every evidence record references real work)."""
    from backend.app.db.models import AuditRecord, Prediction

    prediction_ids = {row[0] for row in db.execute(select(Prediction.id)).all()}
    rows = db.execute(select(AuditRecord.sequence_number, AuditRecord.prediction_id)).all()
    return [
        _finding("audit_orphan_reference", SEVERITY_ERROR,
                 f"Audit record seq {seq} references prediction {pid} which no longer exists.",
                 sequence_number=seq, prediction_id=pid)
        for seq, pid in rows if pid not in prediction_ids
    ]


def audit_database(db: Session) -> Dict[str, Any]:
    """Run every integrity check and aggregate a report."""
    from backend.app.cryptography.verifier import verify_ledger
    from backend.app.db.models import AuditRecord, ModelRecord, Prediction

    findings: List[Dict[str, Any]] = []
    findings += check_orphan_predictions(db)
    findings += check_duplicate_audit_sequences(db)
    findings += check_audit_sequence_contiguity(db)
    findings += check_temporal_consistency(db)
    findings += check_audit_reference_integrity(db)

    # Full-chain verification: the DB half of invariant 22.1.
    records = db.execute(
        select(AuditRecord).order_by(AuditRecord.sequence_number)
    ).scalars().all()
    chain = verify_ledger(list(records))
    if not chain.verified:
        findings.append(_finding(
            "audit_chain_broken", SEVERITY_ERROR,
            f"Hash chain verification failed: {len(chain.failed_records)} record(s) anomalous.",
            first_failures=chain.failed_records[:5],
        ))

    errors = [f for f in findings if f["severity"] == SEVERITY_ERROR]
    warnings = [f for f in findings if f["severity"] == SEVERITY_WARN]
    return {
        "consistent": not errors,
        "total_records_checked": {
            "audit": len(records),
            "models": db.execute(select(func.count(ModelRecord.id))).scalar() or 0,
            "predictions": db.execute(select(func.count(Prediction.id))).scalar() or 0,
        },
        "summary": {"errors": len(errors), "warnings": len(warnings)},
        "findings": findings,
        "chain_verification": chain.to_dict(),
    }
