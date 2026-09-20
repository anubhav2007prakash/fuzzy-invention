# SentinelCrypt AI — API Context

## API Base Route & Conventions
- Base Path: `/api/v1`
- OpenAPI Specification: `/api/v1/openapi.json`
- Standard Response: JSON with consistent HTTP status codes.

## Endpoints Inventory

### Health
- `GET /api/v1/health` — System and engine status check.

### Datasets
- `POST /api/v1/datasets` — Register and validate a dataset file.
- `GET /api/v1/datasets` — List registered datasets.
- `GET /api/v1/datasets/{dataset_id}` — Retrieve dataset metadata and column schema.

### Models
- `POST /api/v1/models/train` — Asynchronously trigger model training (LR / RF).
- `GET /api/v1/models` — List trained models.
- `GET /api/v1/models/{model_id}` — Get model status, hyperparameters, and artifact URI.
- `GET /api/v1/models/{model_id}/metrics` — Get detailed evaluation metrics and confusion matrix.

### Predictions
- `POST /api/v1/predictions` — Real-time inference + SHAP explanation + audit hash chain anchoring.
- `POST /api/v1/predictions/batch` — High-throughput batch inference with sequential audit linkage.
- `GET /api/v1/predictions/{prediction_id}` — Retrieve prediction details and status.

### Explainability
- `GET /api/v1/predictions/{prediction_id}/explanation` — Retrieve local SHAP feature attributions and stability metrics.

### Audit Ledger
- `GET /api/v1/audit/records` — Query paginated immutable audit ledger entries.
- `GET /api/v1/audit/records/{record_id}` — Retrieve full cryptographic proof and canonical JSON payload.
- `POST /api/v1/audit/verify` — Execute full ledger integrity verification and return tamper detection report.

### Experiments
- `POST /api/v1/experiments` — Trigger research experiment execution (EXP-A, EXP-B, EXP-C, EXP-D).
- `GET /api/v1/experiments` — List research experiments.
- `GET /api/v1/experiments/{experiment_id}` — Retrieve experiment metrics, evaluation matrices, and result tables.
