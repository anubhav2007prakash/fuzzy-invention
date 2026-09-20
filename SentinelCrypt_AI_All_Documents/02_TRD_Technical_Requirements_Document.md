# SentinelCrypt AI
## Technical Requirements Document (TRD)

**Version:** 1.0  
**Status:** Proposed  
**Architecture:** Modular monolith with separate React frontend and FastAPI backend

---

## 1. Technical Objectives

The system shall provide a reproducible pipeline for network intrusion detection using public datasets, explainable ML, and tamper-evident audit records.

## 2. Recommended Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| ML | scikit-learn, pandas, NumPy |
| Explainability | SHAP |
| Backend | FastAPI, Pydantic |
| Database | SQLite initially |
| Frontend | React, JavaScript |
| Charts | Recharts |
| Cryptography | hashlib, hmac, secrets |
| Testing | pytest |
| Documentation | Markdown, OpenAPI |
| Version control | Git and GitHub |
| Environment | Windows + WSL or Linux |

## 3. Functional Requirements

### FR-01: Dataset ingestion

The system shall:

- Accept supported CSV datasets.
- Validate required columns.
- Detect missing values.
- Display row count and label distribution.
- Store dataset metadata.
- Reject unsupported or malformed files.

### FR-02: Preprocessing

The system shall:

- Separate features and target labels.
- Handle missing values.
- Encode categorical values where required.
- Scale numerical features where required.
- Fit transformations only on training data.
- Save the preprocessing pipeline with the model.

### FR-03: Model training

The system shall initially support:

- Logistic Regression.
- Random Forest.

Optional later models:

- Gradient Boosting.
- XGBoost, if dependency and time constraints permit.

The system shall record:

- Model name.
- Model version.
- Dataset identifier.
- Training configuration.
- Random seed.
- Training timestamp.
- Evaluation metrics.

### FR-04: Prediction

The system shall:

- Accept a single network-flow feature vector.
- Validate feature names and types.
- Return predicted class.
- Return class probabilities when supported.
- Return model version.
- Generate a unique prediction identifier.

### FR-05: Explainability

The system shall:

- Generate global feature importance.
- Generate local feature contributions.
- Identify the most influential features.
- Store explanation metadata.
- Clearly state that explanations are model-dependent.

### FR-06: Audit ledger

Each audit record shall include:

- Record ID.
- Prediction ID.
- Model version.
- Dataset or sample reference.
- Predicted class.
- Probability information, where available.
- Explanation summary.
- Timestamp.
- Previous record hash.
- Current record hash.

### FR-07: Verification

The system shall:

- Recalculate record hashes.
- Verify previous-hash links.
- Detect changed content.
- Detect broken chain order.
- Return a clear verification report.

### FR-08: Research evaluation

The system shall support:

- Train/test evaluation.
- Precision.
- Recall.
- F1-score.
- Accuracy.
- Confusion matrix.
- False-positive rate.
- Model comparison.
- Optional cross-dataset evaluation.

## 4. Non-Functional Requirements

### NFR-01: Reproducibility

The same dataset, configuration, and random seed should produce reproducible results within documented environment constraints.

### NFR-02: Security

- Validate all API input.
- Do not execute uploaded files.
- Do not expose secrets in source code.
- Do not log sensitive raw traffic unnecessarily.
- Use safe file names and controlled upload directories.
- Keep the prototype local by default.

### NFR-03: Performance

For the initial prototype:

- Single-record prediction should normally complete within a few seconds.
- Ledger verification should support at least 10,000 records in a local test.
- Dashboard pages should remain usable on a normal laptop.

These are engineering targets, not measured results.

### NFR-04: Maintainability

- Separate data, model, explanation, audit, and API modules.
- Use type hints.
- Use clear exception handling.
- Write unit tests for critical functions.
- Maintain a changelog.

### NFR-05: Usability

A new user should be able to:

1. Install dependencies.
2. Start backend.
3. Start frontend.
4. Load a sample dataset.
5. Run a prediction.
6. Verify an audit record.

## 5. API Requirements

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/datasets/upload` | Upload supported dataset |
| GET | `/datasets` | List datasets |
| GET | `/datasets/{id}` | Dataset details |
| POST | `/models/train` | Train model |
| GET | `/models` | List trained models |
| GET | `/models/{id}/metrics` | Model metrics |
| POST | `/predict` | Predict one flow |
| POST | `/predict/batch` | Predict multiple flows |
| GET | `/predictions/{id}` | Prediction details |
| GET | `/predictions/{id}/explanation` | Explanation |
| GET | `/audit/records` | List audit records |
| GET | `/audit/records/{id}` | Get audit record |
| POST | `/audit/verify` | Verify ledger |
| GET | `/experiments` | List experiments |

## 6. Error Handling

Use consistent responses:

```json
{
  "error": {
    "code": "INVALID_DATASET",
    "message": "Required target column was not found.",
    "details": {}
  }
}
```

Suggested error codes:

- `INVALID_DATASET`
- `UNSUPPORTED_FORMAT`
- `INVALID_FEATURES`
- `MODEL_NOT_FOUND`
- `PREDICTION_FAILED`
- `EXPLANATION_FAILED`
- `LEDGER_VERIFICATION_FAILED`
- `INTERNAL_ERROR`

## 7. Testing Requirements

### Unit tests

- Dataset validation.
- Preprocessing behavior.
- Model loading.
- Prediction schema.
- Hash determinism.
- Hash-chain verification.
- Tamper detection.

### Integration tests

- Upload dataset → train model.
- Train model → prediction.
- Prediction → explanation.
- Prediction → audit record.
- Audit record → verification.

### Research validation

- Compare at least two models.
- Report class-wise metrics.
- Record experiment configurations.
- Avoid test-set contamination.
