"""Leakage-safe preprocessing pipeline for network flow datasets.

Rules
-----
- All transformers (imputer, scaler, encoder) are fitted **only** on X_train.
- X_test is transformed using already-fitted objects (never re-fitted).
- Categorical columns are identified automatically.
- Infinite values are replaced before imputation.
- Pipeline state is serialised to disk with joblib for reproducibility.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler, RobustScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn import set_config

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)
set_config(transform_output="default")


# Columns to always drop (IDs, metadata, raw IP strings common in flow datasets)
_DROP_PATTERNS = [
    "id", "uid", "srcip", "dstip", "sport", "dsport",
    "stime", "ltime", "starttime", "lasttime", "timestamp",
]


class PreprocessingResult:
    """Holds the split data and fitted artefact metadata."""

    def __init__(
        self,
        X_train: np.ndarray,
        X_test: np.ndarray,
        y_train: np.ndarray,
        y_test: np.ndarray,
        feature_names: List[str],
        label_encoder: LabelEncoder,
        pipeline: Pipeline,
        pipeline_path: str,
        label_encoder_path: str,
        feature_schema: List[Dict[str, str]],
        random_seed: int,
        train_ratio: float,
    ):
        self.X_train = X_train
        self.X_test = X_test
        self.y_train = y_train
        self.y_test = y_test
        self.feature_names = feature_names
        self.label_encoder = label_encoder
        self.pipeline = pipeline
        self.pipeline_path = pipeline_path
        self.label_encoder_path = label_encoder_path
        self.feature_schema = feature_schema
        self.random_seed = random_seed
        self.train_ratio = train_ratio


def _is_string_like(series: pd.Series) -> bool:
    """Return True for object, str, or Arrow-backed string dtypes (pandas 2+)."""
    import pandas.api.types as pat
    if pat.is_object_dtype(series):
        return True
    if pat.is_string_dtype(series):
        return True
    # Arrow-backed string: dtype name is 'string[pyarrow]' or ArrowDtype
    dtype_name = str(series.dtype).lower()
    return "string" in dtype_name or "large_string" in dtype_name


def _identify_columns(df: pd.DataFrame, target_column: str) -> Tuple[List[str], List[str], List[str]]:
    """Return (feature_cols, numeric_cols, categorical_cols) after dropping metadata."""
    drop_cols = set()
    for col in df.columns:
        cl = col.strip().lower()
        if any(pat == cl for pat in _DROP_PATTERNS):
            drop_cols.add(col)
    drop_cols.add(target_column)

    feature_cols = [c for c in df.columns if c not in drop_cols]
    categorical_cols = [c for c in feature_cols if _is_string_like(df[c])]
    numeric_cols = [c for c in feature_cols if c not in categorical_cols]

    return feature_cols, numeric_cols, categorical_cols


def _encode_categoricals(
    df: pd.DataFrame,
    categorical_cols: List[str],
    fit_encoders: Optional[Dict[str, LabelEncoder]] = None,
) -> Tuple[pd.DataFrame, Dict[str, LabelEncoder]]:
    """Label-encode categorical columns.

    Unseen test values → -1 (not re-fitted).
    Always produces plain int64 numpy-backed Series, even on pandas with
    Arrow-backed string storage.
    """
    df = df.copy()
    encoders: Dict[str, LabelEncoder] = fit_encoders or {}

    for col in categorical_cols:
        raw = df[col].astype(str).fillna("unknown").tolist()   # plain Python list

        if fit_encoders is None:                               # fitting phase
            le = LabelEncoder()
            le.fit(raw)
            encoders[col] = le
        else:
            le = encoders[col]

        classes_set = set(le.classes_)
        encoded: List[int] = [
            int(le.transform([v])[0]) if v in classes_set else -1
            for v in raw
        ]
        # Assign as plain numpy int64 — avoids Arrow/object dtype retention
        df[col] = pd.array(encoded, dtype="int64")

    return df, encoders


def build_preprocessing_pipeline(
    df: pd.DataFrame,
    target_column: str,
    random_seed: int = 42,
    train_ratio: float = 0.8,
    scaler_type: str = "robust",    # "robust" or "standard"
    save_dir: Optional[Path] = None,
    artifact_name: str = "preprocessing",
) -> PreprocessingResult:
    """
    Execute the full leakage-safe preprocessing pipeline:

    1. Drop metadata columns.
    2. Handle infinity values → NaN.
    3. Encode target labels.
    4. Stratified train/test split (fitted on nothing yet).
    5. Encode categorical features using **train encoders only**.
    6. Fit imputer on X_train, transform both splits.
    7. Fit scaler on X_train, transform both splits.
    8. Serialise pipeline artefacts.
    """
    save_dir = save_dir or settings.MODELS_ARTIFACTS_DIR
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Identify columns ──────────────────────────────────────────────
    feature_cols, numeric_cols, categorical_cols = _identify_columns(df, target_column)
    logger.info("Features: %d total (%d numeric, %d categorical)",
                len(feature_cols), len(numeric_cols), len(categorical_cols))

    # ── Step 2: Replace ±inf with NaN ─────────────────────────────────────────
    df = df.copy()
    df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], np.nan)

    # ── Step 3: Encode target labels ──────────────────────────────────────────
    target_series = df[target_column].astype(str).fillna("unknown")
    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(target_series)
    logger.info("Label classes: %s", list(label_encoder.classes_))

    X_raw = df[feature_cols].copy()

    # ── Step 4: Stratified split — BEFORE fitting any transformer ─────────────
    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X_raw, y_encoded,
        test_size=1.0 - train_ratio,
        random_state=random_seed,
        stratify=y_encoded,
    )
    logger.info("Split — train: %d rows, test: %d rows", len(X_train_raw), len(X_test_raw))

    # ── Step 5: Encode categoricals (fit on train only) ───────────────────────
    X_train_enc, cat_encoders = _encode_categoricals(X_train_raw, categorical_cols)
    X_test_enc, _ = _encode_categoricals(X_test_raw, categorical_cols, fit_encoders=cat_encoders)

    # ── Step 6: Convert to pure numpy float64 ────────────────────────────────
    # We extract each column individually to bypass pandas Arrow-backed string
    # dtype, which blocks bulk DataFrame.astype(float64) on pandas 2+ with
    # future.infer_string = True.
    def _df_to_float64(df_enc: pd.DataFrame, cols: List[str]) -> np.ndarray:
        arrays = []
        for c in cols:
            series = df_enc[c]
            # Already numeric — to_numpy with float64
            try:
                arr = series.to_numpy(dtype=np.float64, na_value=np.nan)
            except (ValueError, TypeError):
                # Fallback: convert via Python list (handles any edge-case dtype)
                arr = np.array(
                    [np.nan if pd.isna(v) else float(v) for v in series.tolist()],
                    dtype=np.float64,
                )
            arrays.append(arr)
        return np.column_stack(arrays) if arrays else np.empty((len(df_enc), 0), dtype=np.float64)

    X_train_num = _df_to_float64(X_train_enc, feature_cols)
    X_test_num = _df_to_float64(X_test_enc, feature_cols)

    # ── Step 7: Impute missing values (fit on train only) ─────────────────────
    imputer = SimpleImputer(strategy="median")
    X_train_imp = imputer.fit_transform(X_train_num)
    X_test_imp = imputer.transform(X_test_num)

    # ── Step 8: Scale (fit on train only) ─────────────────────────────────────
    ScalerClass = RobustScaler if scaler_type == "robust" else StandardScaler
    scaler = ScalerClass()
    X_train_scaled = scaler.fit_transform(X_train_imp)
    X_test_scaled = scaler.transform(X_test_imp)

    # ── Step 9: Build sklearn Pipeline wrapper for inference ──────────────────
    # The pipeline is used at inference time to transform a single sample
    pipeline = Pipeline([
        ("imputer", imputer),
        ("scaler", scaler),
    ])

    # ── Step 9: Serialise artefacts ───────────────────────────────────────────
    pipeline_path = save_dir / f"{artifact_name}_pipeline.pkl"
    label_encoder_path = save_dir / f"{artifact_name}_label_encoder.pkl"
    cat_encoders_path = save_dir / f"{artifact_name}_cat_encoders.pkl"

    with open(pipeline_path, "wb") as f:
        pickle.dump({"pipeline": pipeline, "cat_encoders": cat_encoders,
                     "feature_cols": feature_cols}, f)
    with open(label_encoder_path, "wb") as f:
        pickle.dump(label_encoder, f)
    with open(cat_encoders_path, "wb") as f:
        pickle.dump(cat_encoders, f)

    logger.info("Artefacts saved to %s", save_dir)

    # ── Step 10: Feature schema (for API validation) ──────────────────────────
    feature_schema = []
    for col in feature_cols:
        dtype = "categorical" if col in categorical_cols else "numeric"
        feature_schema.append({"name": col, "type": dtype})

    return PreprocessingResult(
        X_train=X_train_scaled,
        X_test=X_test_scaled,
        y_train=y_train,
        y_test=y_test,
        feature_names=feature_cols,
        label_encoder=label_encoder,
        pipeline=pipeline,
        pipeline_path=str(pipeline_path),
        label_encoder_path=str(label_encoder_path),
        feature_schema=feature_schema,
        random_seed=random_seed,
        train_ratio=train_ratio,
    )


def transform_single_sample(
    sample: Dict,
    pipeline_path: str,
    label_encoder_path: Optional[str] = None,
) -> Tuple[np.ndarray, List[str]]:
    """
    Transform a single inference sample using saved artefacts.

    Returns (X_transformed, feature_names).
    """
    with open(pipeline_path, "rb") as f:
        artefacts = pickle.load(f)

    pipeline: Pipeline = artefacts["pipeline"]
    cat_encoders: Dict[str, LabelEncoder] = artefacts.get("cat_encoders", {})
    feature_cols: List[str] = artefacts["feature_cols"]

    # Build a single-row DataFrame with the expected features
    row: Dict = {}
    for col in feature_cols:
        row[col] = sample.get(col, np.nan)
    df_single = pd.DataFrame([row])

    # Replace inf
    df_single = df_single.replace([np.inf, -np.inf], np.nan)

    # Encode categoricals using **saved** encoders (no re-fit)
    categorical_cols = list(cat_encoders.keys())
    df_single, _ = _encode_categoricals(df_single, categorical_cols, fit_encoders=cat_encoders)

    X = df_single[feature_cols].astype(np.float64).values
    X_transformed = pipeline.transform(X)
    return X_transformed, feature_cols
