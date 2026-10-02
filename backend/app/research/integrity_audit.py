"""Read-only integrity checks for SentinelCrypt's relational database."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import UniqueConstraint, func, inspect as sa_inspect, select
from sqlalchemy.orm import Session

from backend.app.db.database import Base

_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_DATA_RAW_DIR = Path(__file__).parents[3] / "data" / "raw"
_FUTURE_CLOCK_TOLERANCE_SECONDS = 5


def _finding(
    issue_type: str,
    severity: str,
    table: str,
    description: str,
    recommendation: str,
    *,
    affected_rows: int = 1,
    affected_ids: list[Any] | None = None,
) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "type": issue_type,
        "severity": severity,
        "table": table,
        "description": description,
        "affected_rows": affected_rows,
        "recommendation": recommendation,
    }
    if affected_ids:
        finding["affected_ids"] = affected_ids[:10]
    return finding


def _mapped_models() -> list[type]:
    return sorted(
        (mapper.class_ for mapper in Base.registry.mappers),
        key=lambda model: model.__tablename__,
    )


def _check_foreign_keys(
    db: Session, model_class: type, rows: list[Any]
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    table_name = model_class.__tablename__
    mapper = sa_inspect(model_class)

    for column in mapper.columns:
        for foreign_key in column.foreign_keys:
            target_column = foreign_key.column
            referenced_values = set(
                db.execute(select(target_column)).scalars().all()
            )
            orphans = [
                row
                for row in rows
                if (value := getattr(row, column.key)) is not None
                and value not in referenced_values
            ]
            if orphans:
                issues.append(
                    _finding(
                        "orphan_foreign_key",
                        "high",
                        table_name,
                        f"{len(orphans)} row(s) in {table_name}.{column.name} reference missing "
                        f"{target_column.table.name} records.",
                        "Restore the referenced record or correct/remove the invalid reference.",
                        affected_rows=len(orphans),
                        affected_ids=[getattr(row, _primary_key_name(model_class), None) for row in orphans],
                    )
                )
    return issues


def _primary_key_name(model_class: type) -> str:
    primary_keys = sa_inspect(model_class).primary_key
    return primary_keys[0].key if primary_keys else "id"


def _check_unique_identifiers(
    db: Session, model_class: type, rows: list[Any]
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    table = sa_inspect(model_class).local_table
    table_name = table.name
    constraints: dict[tuple[str, ...], str] = {
        (column.key,): "primary_key" for column in table.primary_key.columns
    }
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint):
            keys = tuple(column.key for column in constraint.columns)
            constraints[keys] = "unique_constraint"
    for index in table.indexes:
        if index.unique:
            keys = tuple(column.key for column in index.columns)
            constraints[keys] = "unique_index"

    for keys, constraint_type in constraints.items():
        columns = [getattr(model_class, key) for key in keys]
        query = select(*columns, func.count()).group_by(*columns).having(func.count() > 1)
        duplicates = db.execute(query).all()
        if duplicates:
            issues.append(
                _finding(
                    "duplicate_identifier",
                    "high",
                    table_name,
                    f"{len(duplicates)} duplicate value group(s) violate a {constraint_type} "
                    f"constraint on {', '.join(keys)}.",
                    "Investigate the duplicate rows and restore the database's uniqueness constraints.",
                    affected_rows=sum(int(row[-1]) for row in duplicates),
                    affected_ids=[list(row[:-1]) for row in duplicates],
                )
            )
    return issues


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _check_row_invariants(model_class: type, rows: list[Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    table_name = model_class.__tablename__
    pk_name = _primary_key_name(model_class)
    now = datetime.now(timezone.utc)

    for row in rows:
        record_id = getattr(row, pk_name, None)
        created_at = getattr(row, "created_at", None)
        updated_at = getattr(row, "updated_at", None)
        if isinstance(created_at, datetime):
            if (_as_utc(created_at) - now).total_seconds() > _FUTURE_CLOCK_TOLERANCE_SECONDS:
                issues.append(
                    _finding(
                        "inconsistent_timestamp",
                        "medium",
                        table_name,
                        f"Record {record_id} has a creation timestamp in the future.",
                        "Verify the host clock and correct the timestamp if it is invalid.",
                        affected_ids=[record_id],
                    )
                )
            if isinstance(updated_at, datetime) and _as_utc(updated_at) < _as_utc(created_at):
                issues.append(
                    _finding(
                        "inconsistent_timestamp",
                        "high",
                        table_name,
                        f"Record {record_id} was updated before it was created.",
                        "Correct the record timestamps after checking their provenance.",
                        affected_ids=[record_id],
                    )
                )

        if model_class.__name__ == "ArtifactLineage":
            if not _SHA256_PATTERN.fullmatch(row.sha256 or ""):
                issues.append(
                    _finding(
                        "invalid_artifact_digest",
                        "high",
                        table_name,
                        f"Artifact {record_id} has a malformed SHA-256 digest.",
                        "Recompute the digest from the authoritative artifact and investigate changes.",
                        affected_ids=[record_id],
                    )
                )
            try:
                metadata = json.loads(row.metadata_json or "{}")
                if not isinstance(metadata, dict):
                    raise ValueError("metadata must be a JSON object")
            except (json.JSONDecodeError, TypeError, ValueError):
                issues.append(
                    _finding(
                        "invalid_metadata",
                        "medium",
                        table_name,
                        f"Artifact {record_id} has invalid lineage metadata.",
                        "Restore metadata_json as a valid JSON object.",
                        affected_ids=[record_id],
                    )
                )

        if model_class.__name__ == "Prediction" and row.model_id is None:
            issues.append(
                _finding(
                    "impossible_state",
                    "high",
                    table_name,
                    f"Prediction {record_id} has no associated model.",
                    "Restore a valid model reference or remove the invalid prediction.",
                    affected_ids=[record_id],
                )
            )

        if model_class.__name__ == "FalsificationResult" and row.run_index < 0:
            issues.append(
                _finding(
                    "impossible_state",
                    "medium",
                    table_name,
                    f"Falsification result {record_id} has a negative run index.",
                    "Correct the run index to a non-negative value.",
                    affected_ids=[record_id],
                )
            )

    return issues


def _check_artifact_references(rows_by_model: dict[type, list[Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    def is_file(path: Path) -> bool:
        try:
            return path.is_file()
        except (OSError, ValueError, RuntimeError):
            return False

    for model_class, rows in rows_by_model.items():
        if model_class.__name__ == "Dataset":
            for row in rows:
                filename = row.file_name or ""
                if (
                    not isinstance(filename, str)
                    or not filename
                    or "\x00" in filename
                    or Path(filename).is_absolute()
                    or Path(filename).name != filename
                    or filename in {".", ".."}
                ):
                    issues.append(
                        _finding(
                            "invalid_artifact_reference",
                            "high",
                            model_class.__tablename__,
                            f"Dataset {row.id} has an unsafe or empty stored filename.",
                            "Replace the reference with a server-generated filename contained in data/raw.",
                            affected_ids=[row.id],
                        )
                    )
                    continue
                try:
                    root = _DATA_RAW_DIR.resolve()
                    candidate = (root / filename).resolve()
                    candidate.relative_to(root)
                    exists = is_file(candidate)
                except (OSError, ValueError, RuntimeError):
                    exists = False
                if not exists:
                    issues.append(
                        _finding(
                            "missing_artifact",
                            "high",
                            model_class.__tablename__,
                            f"Dataset {row.id} references a file that is missing from the configured raw-data directory.",
                            "Restore the referenced dataset file or correct the dataset registration.",
                            affected_ids=[row.id],
                        )
                    )
        elif model_class.__name__ == "ModelRecord":
            for row in rows:
                for attribute in ("artifact_path", "preprocessing_path"):
                    path_value = getattr(row, attribute, None)
                    if (
                        not isinstance(path_value, str)
                        or not path_value
                        or not is_file(Path(path_value))
                    ):
                        issues.append(
                            _finding(
                                "missing_artifact",
                                "high",
                                model_class.__tablename__,
                                f"Model {row.id} references a missing {attribute} file.",
                                "Restore the artifact or correct its registered path.",
                                affected_ids=[row.id],
                            )
                        )
    return issues


def _check_domain_relationships(
    rows_by_model: dict[type, list[Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    models_by_name = {model.__name__: model for model in rows_by_model}
    rows_by_name = {
        model.__name__: rows for model, rows in rows_by_model.items()
    }

    predictions = rows_by_name.get("Prediction", [])
    audit_prediction_ids = {
        row.prediction_id for row in rows_by_name.get("AuditRecord", [])
    }
    for prediction in predictions:
        if prediction.id not in audit_prediction_ids:
            issues.append(
                _finding(
                    "missing_provenance",
                    "high",
                    models_by_name["Prediction"].__tablename__,
                    f"Prediction {prediction.id} has no cryptographic audit record.",
                    "Create the expected audit evidence through the application workflow or investigate the missing record.",
                    affected_ids=[prediction.id],
                )
            )

    experiments = {
        row.id: row for row in rows_by_name.get("Experiment", [])
    }
    models = {row.id: row for row in rows_by_name.get("ModelRecord", [])}
    for evaluation in rows_by_name.get("ModelEvaluation", []):
        experiment = experiments.get(evaluation.experiment_id)
        model = models.get(evaluation.model_id)
        if experiment and experiment.dataset_id != evaluation.dataset_id:
            issues.append(
                _finding(
                    "invalid_relationship",
                    "high",
                    models_by_name["ModelEvaluation"].__tablename__,
                    f"Evaluation {evaluation.id} uses a dataset different from its experiment's dataset.",
                    "Correct the evaluation's experiment or dataset association.",
                    affected_ids=[evaluation.id],
                )
            )
        if model and model.experiment_id and model.experiment_id != evaluation.experiment_id:
            issues.append(
                _finding(
                    "invalid_relationship",
                    "high",
                    models_by_name["ModelEvaluation"].__tablename__,
                    f"Evaluation {evaluation.id} references a model trained by a different experiment.",
                    "Correct the evaluation's model or experiment association.",
                    affected_ids=[evaluation.id],
                )
            )

    experiment_ids = set(experiments)
    prediction_ids = {
        row.id for row in rows_by_name.get("Prediction", [])
    }
    audit_ids = {row.id for row in rows_by_name.get("AuditRecord", [])}
    model_ids = set(models)
    soft_references = (
        ("AnalystReview", "prediction_id", prediction_ids),
        ("AnalystReview", "model_id", model_ids),
        ("AnalystReview", "audit_record_id", audit_ids),
        ("ExperimentComment", "experiment_id", experiment_ids),
        ("ExperimentReviewState", "experiment_id", experiment_ids),
    )
    for model_name, field_name, existing_ids in soft_references:
        mapped_model = models_by_name.get(model_name)
        if mapped_model is None:
            continue
        for row in rows_by_name.get(model_name, []):
            reference_id = getattr(row, field_name, None)
            if reference_id is not None and reference_id not in existing_ids:
                issues.append(
                    _finding(
                        "invalid_relationship",
                        "high",
                        mapped_model.__tablename__,
                        f"{model_name} record {getattr(row, _primary_key_name(mapped_model), '?')} "
                        f"references a missing {field_name.removesuffix('_id')}.",
                        "Restore the referenced record or correct/remove the invalid reference.",
                        affected_ids=[getattr(row, _primary_key_name(mapped_model), None)],
                    )
                )

    lineage_rows = rows_by_name.get("ArtifactLineage", [])
    lineage_by_id = {row.artifact_id: row for row in lineage_rows}
    for artifact in lineage_rows:
        if artifact.experiment_id and artifact.experiment_id not in experiment_ids:
            issues.append(
                _finding(
                    "orphan_foreign_key",
                    "high",
                    models_by_name["ArtifactLineage"].__tablename__,
                    f"Artifact {artifact.artifact_id} references a missing experiment.",
                    "Restore the experiment or correct the artifact's experiment reference.",
                    affected_ids=[artifact.artifact_id],
                )
            )
        parent = lineage_by_id.get(artifact.parent_artifact_id)
        if (
            parent is not None
            and isinstance(artifact.created_at, datetime)
            and isinstance(parent.created_at, datetime)
            and _as_utc(artifact.created_at) < _as_utc(parent.created_at)
        ):
            issues.append(
                _finding(
                    "inconsistent_timestamp",
                    "high",
                    models_by_name["ArtifactLineage"].__tablename__,
                    f"Artifact {artifact.artifact_id} predates its declared parent.",
                    "Verify artifact ancestry and correct timestamps only from authoritative provenance.",
                    affected_ids=[artifact.artifact_id, parent.artifact_id],
                )
            )

    completed: set[str] = set()
    for artifact_id in lineage_by_id:
        path: set[str] = set()
        current_id: str | None = artifact_id
        while current_id is not None and current_id in lineage_by_id:
            if current_id in path:
                issues.append(
                    _finding(
                        "invalid_relationship",
                        "high",
                        models_by_name["ArtifactLineage"].__tablename__,
                        f"Artifact lineage contains a parent cycle involving {current_id}.",
                        "Break the cycle and verify all affected artifact ancestry.",
                        affected_ids=sorted(path),
                    )
                )
                break
            if current_id in completed:
                break
            path.add(current_id)
            current_id = lineage_by_id[current_id].parent_artifact_id
        completed.update(path)
    return issues


def audit_database(db: Session) -> dict[str, Any]:
    """Audit mapped SentinelCrypt records without writing to the database."""
    started = time.monotonic()
    models = _mapped_models()
    findings: list[dict[str, Any]] = []
    with db.no_autoflush:
        rows_by_model = {model: db.query(model).all() for model in models}
        for model_class, rows in rows_by_model.items():
            findings.extend(_check_unique_identifiers(db, model_class, rows))
            findings.extend(_check_foreign_keys(db, model_class, rows))
            findings.extend(_check_row_invariants(model_class, rows))
        findings.extend(_check_artifact_references(rows_by_model))
        findings.extend(_check_domain_relationships(rows_by_model))

        # Keep ledger checks independent and include deletion/reordering and hash-chain
        # failures that ordinary relational constraints cannot detect.
        from backend.app.research.db_integrity import audit_database as audit_ledger

        ledger_report = audit_ledger(db)
    ledger_type_map = {
        "audit_sequence_gap": "record_deletion_or_reordering",
        "audit_chain_broken": "hash_chain_invalid",
        "duplicate_audit_sequence": "duplicate_identifier",
        "audit_orphan_reference": "orphan_foreign_key",
        "orphan_prediction": "orphan_foreign_key",
        "temporal_impossible": "inconsistent_timestamp",
    }
    for ledger_finding in ledger_report["findings"]:
        check = ledger_finding["check"]
        findings.append(
            _finding(
                ledger_type_map.get(check, check),
                "high" if ledger_finding["severity"] == "ERROR" else "low",
                "audit_records" if check.startswith("audit_") else "predictions",
                ledger_finding["message"],
                "Investigate the ledger and restore records only from an authoritative source.",
            )
        )

    issues_by_type: dict[str, int] = {}
    issues_by_severity = {"high": 0, "medium": 0, "low": 0}
    details: dict[str, dict[str, Any]] = {}
    for finding in findings:
        issue_type = finding["type"]
        severity = finding["severity"]
        issues_by_type[issue_type] = issues_by_type.get(issue_type, 0) + 1
        issues_by_severity[severity] = issues_by_severity.get(severity, 0) + 1
        table_details = details.setdefault(
            finding["table"], {"issue_count": 0, "issue_types": []}
        )
        table_details["issue_count"] += 1
        table_details["issue_types"].append(issue_type)

    for model_class, rows in rows_by_model.items():
        details.setdefault(
            model_class.__tablename__,
            {"issue_count": 0, "issue_types": []},
        )

    return {
        "audit_id": f"INT-{uuid4()}",
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "tables_checked": len(models),
        "total_issues": len(findings),
        "issues_by_type": issues_by_type,
        "issues_by_severity": issues_by_severity,
        "details": details,
        "findings": findings,
        "summary": [
            f"Total: {len(findings)} integrity issue(s) across {len(models)} tables."
        ],
        "status": "UNHEALTHY" if findings else "HEALTHY",
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
        "read_only": True,
        "ledger_consistent": ledger_report["consistent"],
    }
