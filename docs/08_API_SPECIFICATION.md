# SentinelCrypt AI — API Specification

**Base path:** `/api/v1`

## Endpoints
### Health
`GET /health`

### Datasets
`POST /datasets/register`
`GET /datasets`
`GET /datasets/{dataset_id}`

### Models
`POST /models/train`
`GET /models`
`GET /models/{model_id}`
`GET /models/{model_id}/metrics`

### Prediction
`POST /predict`
`POST /predict/batch`
`GET /predictions/{prediction_id}`
`GET /predictions/{prediction_id}/explanation`

### Audit
`GET /audit/records`
`GET /audit/records/{record_id}`
`POST /audit/verify`

### Experiments
`POST /experiments`
`GET /experiments`
`GET /experiments/{experiment_id}`

## API Rules
Validate with Pydantic; bound batch sizes; reject unsafe paths; use consistent error structures; do not expose unnecessary model internals.

## Example Error
```json
{"error":{"code":"VALIDATION_ERROR","message":"Input schema validation failed"}}
```

FastAPI can generate the OpenAPI specification automatically.
