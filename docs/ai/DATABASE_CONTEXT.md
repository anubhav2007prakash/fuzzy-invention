# SentinelCrypt AI — Database Context

## Frozen Entity Schema & Relationships

```
Dataset (1:N) ──> Model (1:N) ──> Prediction
                                     ├── (1:0..1) ──> Explanation
                                     └── (1:1) ────> AuditRecord

Experiment (1:N) ──> ModelEvaluation
```

## Entity Details
1. **`datasets` (`Dataset`):**
   - `id`: UUID (String 36) PK
   - `name`: String
   - `source_file`: String
   - `row_count`: Integer
   - `feature_count`: Integer
   - `target_column`: String
   - `checksum_sha256`: String (64 chars)
   - `created_at`: DateTime

2. **`models` (`ModelRecord`):**
   - `id`: UUID PK
   - `dataset_id`: FK -> `datasets.id`
   - `model_type`: String (`logistic_regression`, `random_forest`)
   - `hyperparameters`: JSON
   - `status`: String (`training`, `ready`, `failed`)
   - `artifact_path`: String
   - `metrics`: JSON
   - `created_at`: DateTime

3. **`predictions` (`Prediction`):**
   - `id`: UUID PK
   - `model_id`: FK -> `models.id`
   - `input_features`: JSON
   - `prediction_label`: Integer (0=benign, 1=attack)
   - `prediction_probability`: Float
   - `latency_ms`: Float
   - `created_at`: DateTime

4. **`explanations` (`Explanation`):**
   - `id`: UUID PK
   - `prediction_id`: FK -> `predictions.id` (Unique)
   - `method`: String (`TreeSHAP`, `LinearSHAP`)
   - `base_value`: Float
   - `feature_attributions`: JSON
   - `stability_score`: Float
   - `created_at`: DateTime

5. **`audit_records` (`AuditRecord`):**
   - `id`: UUID PK
   - `prediction_id`: FK -> `predictions.id` (Unique)
   - `sequence_number`: BigInteger (monotonic, starting at 1)
   - `previous_hash`: String (64 hex characters)
   - `payload_hash`: String (64 hex characters)
   - `record_hash`: String (64 hex characters)
   - `canonical_payload`: Text
   - `created_at`: DateTime

6. **`experiments` (`Experiment`):**
   - `id`: UUID PK
   - `code`: String (e.g., `EXP-A`)
   - `name`: String
   - `description`: Text
   - `config`: JSON
   - `status`: String (`pending`, `running`, `completed`, `failed`)
   - `created_at`: DateTime

7. **`model_evaluations` (`ModelEvaluation`):**
   - `id`: UUID PK
   - `experiment_id`: FK -> `experiments.id`
   - `model_id`: FK -> `models.id`
   - `dataset_id`: FK -> `datasets.id`
   - `metrics`: JSON (accuracy, precision, recall, f1, roc_auc)
   - `confusion_matrix`: JSON
   - `execution_time_s`: Float
   - `created_at`: DateTime
