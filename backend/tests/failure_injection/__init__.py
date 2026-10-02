"""SentinelCrypt AI — Controlled Failure Injection Test Framework.

This framework provides isolated, reproducible failure injection mechanisms
to test robustness and failure safety across the platform without introducing
production instability.
"""
from __future__ import annotations

from backend.tests.failure_injection.base import BaseFaultInjector
from backend.tests.failure_injection.injectors import (
    CorruptedAuditRecordInjector,
    CorruptedDatasetInjector,
    DatabaseUnavailableInjector,
    IncompleteExperimentInjector,
    InvalidAPIInputInjector,
    MissingConfigurationInjector,
    MissingModelArtifactInjector,
    SHAPFailureInjector,
    UnavailableDependencyInjector,
)
from backend.tests.failure_injection.assertions import (
    FailureVerificationRecord,
    FailureVerificationReport,
    assert_consistent_state,
    assert_evidence_not_corrupted,
    assert_fails_safely,
    assert_meaningful_error,
    assert_no_silent_invalid_results,
)

# Convenient aliases / factory functions
def inject_database_unavailable(db_session=None, app=None, error_message=None):
    kwargs = {}
    if db_session is not None:
        kwargs["db_session"] = db_session
    if app is not None:
        kwargs["app"] = app
    if error_message is not None:
        kwargs["error_message"] = error_message
    return DatabaseUnavailableInjector(**kwargs)


def inject_missing_model_artifact(artifact_path=None, fail_preprocessor=False):
    return MissingModelArtifactInjector(
        artifact_path=artifact_path,
        fail_preprocessor=fail_preprocessor,
    )


def inject_dataset_corruption(file_path=None, corruption_type="tampered_bytes"):
    return CorruptedDatasetInjector(
        file_path=file_path,
        corruption_type=corruption_type,
    )


def inject_audit_corruption(records, attack_type="tamper_payload", target_index=1):
    return CorruptedAuditRecordInjector(
        records=records,
        attack_type=attack_type,
        target_index=target_index,
    )


def inject_shap_failure(error_message=None):
    kwargs = {"error_message": error_message} if error_message else {}
    return SHAPFailureInjector(**kwargs)


def inject_incomplete_experiment(experiment_id="EXP-A", error_message=None):
    kwargs = {"experiment_id": experiment_id}
    if error_message:
        kwargs["error_message"] = error_message
    return IncompleteExperimentInjector(**kwargs)


def inject_missing_configuration(overrides):
    return MissingConfigurationInjector(overrides=overrides)


def inject_unavailable_dependency(module_name="shap", error_message=None):
    return UnavailableDependencyInjector(
        module_name=module_name,
        error_message=error_message,
    )


__all__ = [
    "BaseFaultInjector",
    "DatabaseUnavailableInjector",
    "MissingModelArtifactInjector",
    "CorruptedDatasetInjector",
    "CorruptedAuditRecordInjector",
    "SHAPFailureInjector",
    "IncompleteExperimentInjector",
    "MissingConfigurationInjector",
    "UnavailableDependencyInjector",
    "InvalidAPIInputInjector",
    "FailureVerificationRecord",
    "FailureVerificationReport",
    "assert_consistent_state",
    "assert_evidence_not_corrupted",
    "assert_fails_safely",
    "assert_meaningful_error",
    "assert_no_silent_invalid_results",
    "inject_database_unavailable",
    "inject_missing_model_artifact",
    "inject_dataset_corruption",
    "inject_audit_corruption",
    "inject_shap_failure",
    "inject_incomplete_experiment",
    "inject_missing_configuration",
    "inject_unavailable_dependency",
]
