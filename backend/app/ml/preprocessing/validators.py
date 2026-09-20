"""Dataset validation logic for UNSW-NB15, CICIDS2017, and generic CSV datasets."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from backend.app.core.exceptions import InvalidDatasetError, UnsupportedFormatError


# ── Known UNSW-NB15 feature catalogue ────────────────────────────────────────
UNSW_NB15_REQUIRED = [
    "dur", "proto", "service", "state", "spkts", "dpkts",
    "sbytes", "dbytes", "sttl", "dttl", "sloss", "dloss",
    "sinpkt", "dinpkt", "sjit", "djit", "swin", "stcpb",
    "dtcpb", "dwin", "tcprtt", "synack", "ackdat", "smean",
    "dmean", "trans_depth", "response_body_len", "ct_srv_src",
    "ct_state_ttl", "ct_dst_ltm", "ct_src_dport_ltm",
    "ct_dst_sport_ltm", "ct_dst_src_ltm", "is_ftp_login",
    "ct_ftp_cmd", "ct_flw_http_mthd", "ct_src_ltm",
    "ct_srv_dst", "is_sm_ips_ports",
]
UNSW_NB15_LABEL_COLS = ["label", "attack_cat"]

# ── Known CICIDS2017 feature catalogue (subset of canonical cols) ─────────────
CICIDS_REQUIRED = [
    " Destination Port", " Flow Duration", " Total Fwd Packets",
    " Total Backward Packets", "Total Length of Fwd Packets",
    " Total Length of Bwd Packets",
]
CICIDS_LABEL_COL = " Label"


class ValidationReport:
    """Immutable result of dataset validation."""

    def __init__(
        self,
        valid: bool,
        dataset_name: str,
        row_count: int,
        feature_count: int,
        target_column: str,
        label_distribution: Dict[str, int],
        missing_value_counts: Dict[str, int],
        detected_format: str,
        errors: List[str],
        warnings: List[str],
    ):
        self.valid = valid
        self.dataset_name = dataset_name
        self.row_count = row_count
        self.feature_count = feature_count
        self.target_column = target_column
        self.label_distribution = label_distribution
        self.missing_value_counts = missing_value_counts
        self.detected_format = detected_format
        self.errors = errors
        self.warnings = warnings


def validate_dataset(
    file_content: bytes,
    file_name: str,
    custom_target_column: Optional[str] = None,
) -> tuple[pd.DataFrame, ValidationReport]:
    """
    Validate a CSV dataset.

    Steps
    -----
    1. Parse CSV.
    2. Detect format (UNSW-NB15, CICIDS2017, or generic).
    3. Locate or confirm target/label column.
    4. Compute row count, feature count, label distribution.
    5. Summarise missing values.
    6. Return (DataFrame, ValidationReport).

    Raises
    ------
    UnsupportedFormatError  — if file cannot be parsed as CSV.
    InvalidDatasetError     — if critical required columns are absent.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # ── 1. Parse ──────────────────────────────────────────────────────────────
    if not file_name.lower().endswith(".csv"):
        raise UnsupportedFormatError(f"Only CSV files are supported. Received: {file_name}")

    try:
        df = pd.read_csv(io.BytesIO(file_content), low_memory=False)
    except Exception as exc:
        raise UnsupportedFormatError(f"Could not parse CSV file: {exc}") from exc

    if df.empty:
        raise InvalidDatasetError("Dataset file is empty.")

    cols_lower = {c.strip().lower(): c for c in df.columns}

    # ── 2. Detect format ──────────────────────────────────────────────────────
    unsw_hits = sum(1 for r in UNSW_NB15_REQUIRED if r.lower() in cols_lower)
    cicids_hits = sum(1 for r in CICIDS_REQUIRED if r.strip().lower() in cols_lower)

    if unsw_hits >= 20:
        detected_format = "UNSW-NB15"
    elif cicids_hits >= 4:
        detected_format = "CICIDS2017"
    else:
        detected_format = "GENERIC_CSV"
        warnings.append(
            "Dataset format not recognised as UNSW-NB15 or CICIDS2017. "
            "Treating as generic CSV. Ensure the target column is specified."
        )

    # ── 3. Locate target / label column ───────────────────────────────────────
    target_column: Optional[str] = None

    if custom_target_column:
        if custom_target_column.strip().lower() in cols_lower:
            target_column = cols_lower[custom_target_column.strip().lower()]
        else:
            errors.append(
                f"Specified target column '{custom_target_column}' not found in dataset columns."
            )
    elif detected_format == "UNSW-NB15":
        for candidate in UNSW_NB15_LABEL_COLS:
            if candidate in cols_lower:
                target_column = cols_lower[candidate]
                break
    elif detected_format == "CICIDS2017":
        if CICIDS_LABEL_COL.strip().lower() in cols_lower:
            target_column = cols_lower[CICIDS_LABEL_COL.strip().lower()]
    else:
        for candidate in ["label", "class", "target", "attack", "attack_cat", "attack_type"]:
            if candidate in cols_lower:
                target_column = cols_lower[candidate]
                break

    if target_column is None:
        errors.append(
            "Could not locate a target/label column. "
            "Use the `target_column` parameter to specify one explicitly."
        )

    # ── 4. Feature count (excluding label) ────────────────────────────────────
    feature_cols = [c for c in df.columns if c != target_column]
    feature_count = len(feature_cols)

    # ── 5. Label distribution ─────────────────────────────────────────────────
    label_distribution: Dict[str, int] = {}
    if target_column and target_column in df.columns:
        raw_dist = df[target_column].value_counts().to_dict()
        label_distribution = {str(k): int(v) for k, v in raw_dist.items()}
        n_classes = len(label_distribution)
        if n_classes == 1:
            warnings.append("Dataset contains only one class label. Binary classification requires at least two.")
        if n_classes > 20:
            warnings.append(f"Dataset has {n_classes} distinct classes; this is a multi-class scenario.")

    # ── 6. Missing value summary ──────────────────────────────────────────────
    missing_counts = df.isnull().sum()
    missing_dict: Dict[str, int] = {
        col: int(cnt) for col, cnt in missing_counts.items() if cnt > 0
    }
    if missing_dict:
        total_missing = sum(missing_dict.values())
        warnings.append(
            f"{len(missing_dict)} column(s) contain missing values "
            f"({total_missing} total cells). These will be imputed during preprocessing."
        )

    # ── 7. Size / sanity checks ───────────────────────────────────────────────
    if len(df) < 100:
        warnings.append(f"Dataset is very small ({len(df)} rows). Results may not generalise.")

    if feature_count < 3:
        warnings.append(f"Only {feature_count} feature column(s) found. Consider checking column parsing.")

    # Check for infinite values
    numeric_cols = df.select_dtypes(include="number")
    inf_counts = numeric_cols.isin([float("inf"), float("-inf")]).sum().sum()
    if inf_counts > 0:
        warnings.append(f"{inf_counts} infinite value(s) found. These will be replaced during preprocessing.")

    valid = len(errors) == 0

    report = ValidationReport(
        valid=valid,
        dataset_name=Path(file_name).stem,
        row_count=len(df),
        feature_count=feature_count,
        target_column=target_column or "",
        label_distribution=label_distribution,
        missing_value_counts=missing_dict,
        detected_format=detected_format,
        errors=errors,
        warnings=warnings,
    )

    if not valid:
        raise InvalidDatasetError(
            f"Dataset validation failed: {'; '.join(errors)}"
        )

    return df, report
