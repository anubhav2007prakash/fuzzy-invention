"""Persistent, integrity-checked lineage for application-generated artifacts."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session

from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hashing import sha256_hash
from backend.app.db.models import ArtifactLineage

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class LineageIntegrityError(ValueError):
    """Raised when an artifact would introduce invalid or conflicting lineage."""


def _created_at(value: Optional[datetime]) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is not None:
        result = result.astimezone(timezone.utc).replace(tzinfo=None)
    return result


def _metadata(row: ArtifactLineage) -> Dict[str, Any]:
    try:
        value = json.loads(row.metadata_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise LineageIntegrityError(
            f"Artifact '{row.artifact_id}' has invalid metadata JSON."
        ) from exc
    if not isinstance(value, dict):
        raise LineageIntegrityError(
            f"Artifact '{row.artifact_id}' metadata must be a JSON object."
        )
    try:
        canonicalize(value)
    except (TypeError, ValueError) as exc:
        raise LineageIntegrityError(
            f"Artifact '{row.artifact_id}' metadata is not canonicalizable JSON."
        ) from exc
    return value


class ArtifactLineageService:
    def __init__(self, db: Session):
        self.db = db

    def record_chain(self, artifacts: Iterable[Dict[str, Any]]) -> list[ArtifactLineage]:
        """Validate and atomically persist new nodes whose parents already exist."""
        entries = list(artifacts)
        if not entries:
            return []

        existing_rows = {
            row.artifact_id: row
            for row in self.db.query(ArtifactLineage).all()
        }
        pending: Dict[str, ArtifactLineage] = {}

        for item in entries:
            artifact_id = item.get("artifact_id")
            artifact_type = item.get("artifact_type")
            digest = item.get("sha256")
            parent_id = item.get("parent_artifact_id")
            version = item.get("version")
            metadata = item.get("metadata", {})

            if not isinstance(artifact_id, str) or not artifact_id.strip():
                raise LineageIntegrityError("artifact_id must be a non-empty string.")
            if artifact_id in pending:
                raise LineageIntegrityError(f"Duplicate artifact_id '{artifact_id}' in chain.")
            if not isinstance(artifact_type, str) or not artifact_type.strip():
                raise LineageIntegrityError(f"Artifact '{artifact_id}' requires an artifact_type.")
            if not isinstance(version, str) or not version.strip():
                raise LineageIntegrityError(f"Artifact '{artifact_id}' requires a version.")
            if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
                raise LineageIntegrityError(
                    f"Artifact '{artifact_id}' requires a lowercase SHA-256 digest."
                )
            if not isinstance(metadata, dict):
                raise LineageIntegrityError(f"Artifact '{artifact_id}' metadata must be an object.")
            git_commit = item.get("git_commit")
            if git_commit is not None and (
                not isinstance(git_commit, str) or not git_commit or len(git_commit) > 64
            ):
                raise LineageIntegrityError(
                    f"Artifact '{artifact_id}' has an invalid Git commit identifier."
                )
            if parent_id is not None and parent_id not in existing_rows and parent_id not in pending:
                raise LineageIntegrityError(
                    f"Parent artifact '{parent_id}' for '{artifact_id}' does not exist."
                )

            previous = existing_rows.get(artifact_id)
            requested_time = item.get("created_at")
            created_at = _created_at(
                requested_time if requested_time is not None
                else previous.created_at if previous is not None
                else None
            )
            try:
                metadata_json = canonicalize(metadata)
            except (TypeError, ValueError) as exc:
                raise LineageIntegrityError(
                    f"Artifact '{artifact_id}' metadata is not canonicalizable JSON."
                ) from exc
            row = ArtifactLineage(
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                parent_artifact_id=parent_id,
                created_at=created_at,
                version=version,
                sha256=digest,
                git_commit=git_commit,
                experiment_id=item.get("experiment_id"),
                metadata_json=metadata_json,
            )
            if previous is not None:
                if (
                    previous.artifact_type != row.artifact_type
                    or previous.parent_artifact_id != row.parent_artifact_id
                    or previous.created_at != row.created_at
                    or previous.version != row.version
                    or previous.sha256 != row.sha256
                    or previous.git_commit != row.git_commit
                    or previous.experiment_id != row.experiment_id
                    or _metadata(previous) != metadata
                ):
                    raise LineageIntegrityError(
                        f"Artifact '{artifact_id}' already exists with conflicting lineage."
                    )
                pending[artifact_id] = previous
                continue
            pending[artifact_id] = row

        new_rows = [row for key, row in pending.items() if key not in existing_rows]
        try:
            self.db.add_all(new_rows)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return [pending[item["artifact_id"]] for item in entries]

    def graph(self) -> Dict[str, Any]:
        rows = self.db.query(ArtifactLineage).order_by(
            ArtifactLineage.created_at, ArtifactLineage.artifact_id
        ).all()
        by_id = {row.artifact_id: row for row in rows}
        nodes = []
        edges = []
        for row in rows:
            if row.parent_artifact_id and row.parent_artifact_id not in by_id:
                raise LineageIntegrityError(
                    f"Artifact '{row.artifact_id}' references missing parent "
                    f"'{row.parent_artifact_id}'."
                )
            if not _SHA256_RE.fullmatch(row.sha256 or ""):
                raise LineageIntegrityError(
                    f"Artifact '{row.artifact_id}' has an invalid SHA-256 digest."
                )
            nodes.append({
                "artifact_id": row.artifact_id,
                "artifact_type": row.artifact_type,
                "parent_artifact_id": row.parent_artifact_id,
                "created_at": row.created_at.replace(tzinfo=timezone.utc).isoformat(),
                "version": row.version,
                "sha256": row.sha256,
                "git_commit": row.git_commit,
                "experiment_id": row.experiment_id,
                "metadata": _metadata(row),
            })
            if row.parent_artifact_id:
                edges.append({
                    "source": row.parent_artifact_id,
                    "target": row.artifact_id,
                    "type": "derived_from",
                })

        self._assert_acyclic(by_id)
        return {
            "nodes": nodes,
            "edges": edges,
            "integrity": "structurally_valid",
            "integrity_scope": (
                "Checks parent references, acyclic structure, and SHA-256 syntax. "
                "It does not re-hash external files or authenticate database contents."
            ),
        }

    @staticmethod
    def _assert_acyclic(rows: Dict[str, ArtifactLineage]) -> None:
        completed = set()
        for artifact_id in rows:
            path = []
            active = set()
            current: Optional[str] = artifact_id
            while current is not None and current not in completed:
                if current in active:
                    raise LineageIntegrityError(
                        f"Lineage cycle detected at artifact '{current}'."
                    )
                active.add(current)
                path.append(current)
                row = rows.get(current)
                if row is None:
                    raise LineageIntegrityError(
                        f"Artifact '{artifact_id}' references missing parent '{current}'."
                    )
                current = row.parent_artifact_id
            completed.update(path)


def artifact_digest(value: Any) -> str:
    """Hash canonical JSON for an in-memory lineage artifact or metadata snapshot."""
    return sha256_hash(value if isinstance(value, bytes) else canonicalize(value))
