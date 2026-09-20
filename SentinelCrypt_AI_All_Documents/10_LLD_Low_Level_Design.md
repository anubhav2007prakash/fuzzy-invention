# SentinelCrypt AI — Low-Level Design

## Suggested Structure
```text
sentinelcrypt/
  app/
    api/ core/ db/ datasets/ ml/
    prediction/ explainability/ audit/ experiments/
  tests/
  notebooks/
  frontend/
  docs/
```

## Module Interfaces
**DatasetManager:** `register()`, `validate()`, `load()`, `metadata()`

**ModelManager:** `train()`, `evaluate()`, `save()`, `load()`, `metadata()`

**PredictionService:** `validate_input()`, `predict()`, `create_prediction_record()`

**ExplanationService:** `explain()`, `validate_explanation_metadata()`

**AuditLedger:** `canonicalize()`, `append()`, `verify()`

**ExperimentManager:** `create_run()`, `execute()`, `save_result()`

## Audit Algorithm
1. Build a schema-controlled payload.
2. Serialize deterministically.
3. Read the previous digest.
4. Compute SHA-256 over `previous_hash || canonical_payload`.
5. Store the digest.
6. During verification, repeat the process sequentially.

This provides tamper evidence under stated trust assumptions. It is not blockchain and does not guarantee immutability.

## Model Metadata
Store algorithm, dataset ID/hash, preprocessing version, feature schema, seed, timestamp, metrics, and artifact checksum.

## Error Model
Use typed exceptions mapped to safe API responses. Never expose internal paths or stack traces.
