"""Specialized failure injectors for simulating controlled failure modes.

All injectors inherit from BaseFaultInjector and guarantee clean reversion.
"""
from __future__ import annotations

import builtins
import io
import json
import os
import shutil
import subprocess
import tempfile
from inspect import getattr_static
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import patch

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.cryptography.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    calculate_payload_hash,
    calculate_record_hash,
)
from backend.app.ml.registry import ModelRegistry
from backend.tests.failure_injection.base import BaseFaultInjector


# ── 1. Database Unavailable Injector ──────────────────────────────────────────

class DatabaseUnavailableInjector(BaseFaultInjector):
    """Simulates database connectivity loss or operational failure."""

    def __init__(
        self,
        db_session: Optional[Session] = None,
        app: Optional[Any] = None,
        error_message: str = "Simulated database connection loss: operational error",
    ) -> None:
        super().__init__(
            name="database_unavailable",
            description="Simulates database outage or connection refusal.",
        )
        self.db_session = db_session
        self.app = app
        self.error_message = error_message
        self._orig_execute = None
        self._orig_commit = None
        self._orig_dependency = None

    def activate(self) -> None:
        # Patch session if provided
        if self.db_session is not None:
            self._orig_execute = self.db_session.execute
            self._orig_commit = self.db_session.commit

            def failing_execute(*args, **kwargs):
                raise OperationalError(
                    self.error_message, params=None, orig=Exception(self.error_message)
                )

            def failing_commit(*args, **kwargs):
                raise OperationalError(
                    self.error_message, params=None, orig=Exception(self.error_message)
                )

            self.db_session.execute = failing_execute
            self.db_session.commit = failing_commit

        # Patch FastAPI dependency if app provided
        if self.app is not None:
            from backend.app.db.database import get_db

            self._orig_dependency = self.app.dependency_overrides.get(get_db)

            def failing_get_db():
                raise OperationalError(
                    self.error_message, params=None, orig=Exception(self.error_message)
                )

            self.app.dependency_overrides[get_db] = failing_get_db

    def deactivate(self) -> None:
        if self.db_session is not None:
            if self._orig_execute is not None:
                self.db_session.execute = self._orig_execute
            if self._orig_commit is not None:
                self.db_session.commit = self._orig_commit

        if self.app is not None:
            from backend.app.db.database import get_db
            if self._orig_dependency is not None:
                self.app.dependency_overrides[get_db] = self._orig_dependency
            else:
                self.app.dependency_overrides.pop(get_db, None)


# ── 2. Model Artifact Missing Injector ────────────────────────────────────────

class MissingModelArtifactInjector(BaseFaultInjector):
    """Simulates a missing or unreadable model / preprocessor artifact on disk."""

    def __init__(
        self,
        artifact_path: Optional[str | Path] = None,
        fail_preprocessor: bool = False,
        error_message: str = "Simulated missing model artifact file",
    ) -> None:
        super().__init__(
            name="model_artifact_missing",
            description="Simulates missing or deleted model artifact on disk.",
        )
        self.artifact_path = str(artifact_path) if artifact_path else None
        self.fail_preprocessor = fail_preprocessor
        self.error_message = error_message
        self._orig_load_model = None
        self._orig_load_prep = None
        self._orig_load_model_descriptor = None
        self._orig_load_prep_descriptor = None

    def activate(self) -> None:
        self._orig_load_model = ModelRegistry.load_model
        self._orig_load_prep = ModelRegistry.load_preprocessing_pipeline
        self._orig_load_model_descriptor = getattr_static(
            ModelRegistry, "load_model"
        )
        self._orig_load_prep_descriptor = getattr_static(
            ModelRegistry, "load_preprocessing_pipeline"
        )

        orig_load = self._orig_load_model
        target_path = self.artifact_path
        msg = self.error_message

        def mocked_load_model(path: str | Path):
            if target_path is None or str(path) == str(target_path):
                raise FileNotFoundError(f"{msg}: {path}")
            return orig_load(path)

        ModelRegistry.load_model = staticmethod(mocked_load_model)

        if self.fail_preprocessor:
            def mocked_load_prep(path: str | Path):
                raise FileNotFoundError(f"Preprocessing pipeline artifact missing: {path}")

            ModelRegistry.load_preprocessing_pipeline = staticmethod(mocked_load_prep)

    def deactivate(self) -> None:
        if self._orig_load_model_descriptor is not None:
            ModelRegistry.load_model = self._orig_load_model_descriptor
        if self._orig_load_prep_descriptor is not None:
            ModelRegistry.load_preprocessing_pipeline = self._orig_load_prep_descriptor


# ── 3. Dataset Corruption Injector ────────────────────────────────────────────

class CorruptedDatasetInjector(BaseFaultInjector):
    """Simulates dataset file corruption (syntax error, truncated, or hash mismatch)."""

    def __init__(
        self,
        file_path: Optional[str | Path] = None,
        corruption_type: str = "tampered_bytes",
    ) -> None:
        super().__init__(
            name="dataset_corruption",
            description="Simulates malformed CSV or post-registration disk tampering.",
        )
        self.file_path = Path(file_path) if file_path else None
        self.corruption_type = corruption_type
        self._backup_content: Optional[bytes] = None
        self._resolved_path: Optional[Path] = None

    @staticmethod
    def generate_corrupted_csv(kind: str = "syntax_error") -> bytes:
        """Generate corrupted CSV bytes in-memory for testing uploads."""
        if kind == "syntax_error":
            return b"dur,proto,service,state\n0.1,tcp,\"unclosed_string_field\n0.2,udp"
        elif kind == "empty":
            return b""
        elif kind == "truncated":
            return b"dur,proto,service,state,label\n0.1,tcp,"
        elif kind == "missing_columns":
            return b"feature_one,feature_two\n1.0,2.0\n3.0,4.0"
        elif kind == "non_numeric":
            return b"dur,proto,service,state,label\nnot_a_number,tcp,http,FIN,0\n"
        elif kind == "binary_junk":
            return b"\x00\xff\xfe\x01\x10\xde\xad\xbe\xef"
        else:
            return b"corrupted,raw,dataset,content"

    def activate(self) -> None:
        if self.file_path is None:
            return

        supported_corruptions = {
            "tampered_bytes",
            "empty",
            "syntax_error",
            "truncated",
            "missing_columns",
            "non_numeric",
            "binary_junk",
        }
        if self.corruption_type not in supported_corruptions:
            raise ValueError(
                f"Unsupported dataset corruption type: {self.corruption_type}"
            )

        temp_root = Path(tempfile.gettempdir()).resolve()
        target = self.file_path.resolve()
        try:
            target.relative_to(temp_root)
        except ValueError as exc:
            raise ValueError(
                "Dataset corruption is restricted to files under the system "
                f"temporary directory ({temp_root})."
            ) from exc

        if not target.is_file():
            raise FileNotFoundError(f"Dataset test fixture does not exist: {target}")

        self._resolved_path = target
        self._backup_content = target.read_bytes()
        if self.corruption_type == "tampered_bytes":
            # Append corrupt bytes to alter SHA-256 without completely destroying structure
            target.write_bytes(self._backup_content + b"\n# TAMPERED_ROW,0,0,0\n")
        elif self.corruption_type == "empty":
            target.write_bytes(b"")
        else:
            target.write_bytes(self.generate_corrupted_csv(self.corruption_type))

    def deactivate(self) -> None:
        if self._resolved_path and self._backup_content is not None:
            self._resolved_path.write_bytes(self._backup_content)


# ── 4. Audit Record Corruption Injector ───────────────────────────────────────

class CorruptedAuditRecordInjector(BaseFaultInjector):
    """Simulates adversarial attacks and integrity violations on audit ledger records."""

    def __init__(
        self,
        records: List[Any],
        attack_type: str = "tamper_payload",
        target_index: int = 1,
    ) -> None:
        super().__init__(
            name="audit_record_corruption",
            description="Simulates ledger tampering, hash corruption, or sequence gaps.",
        )
        self.records = records
        self.attack_type = attack_type
        self.target_index = target_index
        self._backups: List[Dict[str, Any]] = []

    def activate(self) -> None:
        supported_attacks = {
            "tamper_payload",
            "tamper_record_hash",
            "break_previous_hash",
            "break_sequence",
            "corrupt_json",
        }
        if self.attack_type not in supported_attacks:
            raise ValueError(f"Unsupported audit corruption type: {self.attack_type}")
        if not 0 <= self.target_index < len(self.records):
            raise ValueError(
                f"Audit corruption target index {self.target_index} is out of range "
                f"for {len(self.records)} records."
            )

        # Snapshot records for restoration
        self._backups = [
            {
                "sequence_number": getattr(r, "sequence_number", None),
                "payload_json": getattr(r, "payload_json", None),
                "previous_hash": getattr(r, "previous_hash", None),
                "record_hash": getattr(r, "record_hash", None),
                "payload": getattr(r, "payload", None),
            }
            for r in self.records
        ]

        target = self.records[self.target_index]

        if self.attack_type == "tamper_payload":
            # Change payload contents without updating record_hash
            evil_payload = {"malicious_tamper": True, "altered_by": "adversary"}
            if hasattr(target, "payload"):
                target.payload = evil_payload
            target.payload_json = json.dumps(evil_payload)

        elif self.attack_type == "tamper_record_hash":
            # Tamper the stored record hash
            target.record_hash = "f" * 64

        elif self.attack_type == "break_previous_hash":
            # Break link to previous block
            target.previous_hash = "0" * 64

        elif self.attack_type == "break_sequence":
            # Introduce sequence discontinuity
            target.sequence_number = target.sequence_number + 100

        elif self.attack_type == "corrupt_json":
            # Corrupt payload_json syntax
            target.payload_json = "{bad_json: True, invalid"

    def deactivate(self) -> None:
        if not self._backups:
            return
        for r, backup in zip(self.records, self._backups):
            for attr, val in backup.items():
                if hasattr(r, attr):
                    setattr(r, attr, val)


# ── 5. SHAP Failure Injector ──────────────────────────────────────────────────

class SHAPFailureInjector(BaseFaultInjector):
    """Simulates failures during explainability calculation (e.g. numerical or OOM)."""

    def __init__(
        self,
        error_message: str = "Simulated SHAP computation failure: TreeExplainer dimension mismatch",
    ) -> None:
        super().__init__(
            name="shap_failure",
            description="Simulates SHAP explainer computation failure.",
        )
        self.error_message = error_message
        self._patcher = None

    def activate(self) -> None:
        from backend.app.xai.shap_explainer import SHAPExplainer

        def failing_explain(self_explainer, X, *args, **kwargs):
            raise RuntimeError(self.error_message)

        self._patcher = patch.object(SHAPExplainer, "explain", failing_explain)
        self._patcher.start()

    def deactivate(self) -> None:
        if self._patcher is not None:
            self._patcher.stop()


# ── 6. Incomplete Experiment Injector ─────────────────────────────────────────

class IncompleteExperimentInjector(BaseFaultInjector):
    """Simulates mid-execution failure or abort in an experiment runner."""

    def __init__(
        self,
        experiment_id: str = "EXP-A",
        error_message: str = "Simulated experiment mid-run crash: process aborted",
    ) -> None:
        super().__init__(
            name="incomplete_experiment",
            description="Simulates failure mid-experiment without writing corrupted results.",
        )
        supported_experiments = {"EXP-A", "EXP-F", "EXP-ROBUSTNESS"}
        if experiment_id not in supported_experiments:
            raise ValueError(
                f"Unsupported experiment for failure injection: {experiment_id}"
            )
        self.experiment_id = experiment_id
        self.error_message = error_message
        self._patchers: List[Any] = []

    def activate(self) -> None:
        if self.experiment_id == "EXP-A":
            from backend.app.services.experiment_service import ExperimentService
            def failing_exp_a(*args, **kwargs):
                raise RuntimeError(self.error_message)
            p = patch.object(ExperimentService, "run_exp_a", failing_exp_a)
            p.start()
            self._patchers.append(p)
        elif self.experiment_id == "EXP-F":
            from backend.app.research import ablation
            def failing_ablation(*args, **kwargs):
                raise RuntimeError(self.error_message)
            p = patch.object(ablation, "run_ablation", failing_ablation)
            p.start()
            self._patchers.append(p)
        elif self.experiment_id == "EXP-ROBUSTNESS":
            from backend.app.research import robustness
            def failing_robustness(*args, **kwargs):
                raise RuntimeError(self.error_message)
            p = patch.object(robustness, "run_robustness_study", failing_robustness)
            p.start()
            self._patchers.append(p)

    def deactivate(self) -> None:
        for p in self._patchers:
            p.stop()
        self._patchers.clear()


# ── 7. Missing Configuration Injector ─────────────────────────────────────────

class MissingConfigurationInjector(BaseFaultInjector):
    """Simulates missing or invalid configuration settings."""

    def __init__(self, overrides: Dict[str, Any]) -> None:
        super().__init__(
            name="missing_configuration",
            description="Simulates missing or corrupted environment settings.",
        )
        self.overrides = overrides
        self._saved_values: Dict[str, Any] = {}

    def activate(self) -> None:
        for key, val in self.overrides.items():
            if not hasattr(settings, key):
                raise ValueError(f"Unknown SentinelCrypt setting: {key}")
        for key, val in self.overrides.items():
            self._saved_values[key] = getattr(settings, key)
            setattr(settings, key, val)

    def deactivate(self) -> None:
        for key, val in self._saved_values.items():
            setattr(settings, key, val)


# ── 8. Unavailable Dependency Injector ────────────────────────────────────────

class UnavailableDependencyInjector(BaseFaultInjector):
    """Simulates an unavailable external or optional dependency."""

    def __init__(
        self,
        module_name: str = "shap",
        error_message: Optional[str] = None,
    ) -> None:
        super().__init__(
            name="unavailable_dependency",
            description=f"Simulates missing dependency '{module_name}'.",
        )
        self.module_name = module_name
        self.error_message = error_message or f"No module named '{module_name}'"
        self._orig_import = builtins.__import__

    def activate(self) -> None:
        orig = self._orig_import
        target = self.module_name
        msg = self.error_message

        def failing_import(name, *args, **kwargs):
            if name == target or name.startswith(f"{target}."):
                raise ImportError(msg)
            return orig(name, *args, **kwargs)

        builtins.__import__ = failing_import

    def deactivate(self) -> None:
        builtins.__import__ = self._orig_import


# ── 9. Invalid API Input Injector ─────────────────────────────────────────────

class InvalidAPIInputInjector(BaseFaultInjector):
    """Generates invalid API inputs for boundary and error handling tests."""

    def __init__(self) -> None:
        super().__init__(
            name="invalid_api_input",
            description="Generates malformed, out-of-range, and corrupt API requests.",
        )

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass

    @staticmethod
    def get_invalid_payloads() -> Dict[str, Any]:
        return {
            "non_uuid_id": "not-a-valid-uuid-format-12345",
            "nan_features": {"features": {"dur": float("nan"), "sbytes": 100}},
            "inf_features": {"features": {"dur": float("inf"), "sbytes": 100}},
            "empty_features": {"features": {}},
            "negative_samples": {"n_samples": -50},
            "out_of_bounds_epsilon": {"epsilon_levels": [0.99]},
            "malformed_json_bytes": b"{\"unclosed_key\": 123",
            "invalid_experiment_type": "EXP-NONEXISTENT",
        }
