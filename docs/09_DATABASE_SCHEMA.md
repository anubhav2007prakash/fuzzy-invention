# SentinelCrypt AI
## Backend Schema and Data Model

**Version:** 1.0  
**Database:** SQLite for prototype  
**ORM:** SQLAlchemy recommended  
**API:** FastAPI

---

## 1. Data Model Overview

```text
datasets
   │
   ├──< experiments
   │       │
   │       └──< models
   │                │
   │                └──< predictions
   │                         │
   │                         ├──< explanations
   │                         └──< audit_records
   │
   └──< dataset_features
```

## 2. Entity Definitions

### 2.1 datasets

Stores metadata about uploaded or registered datasets.

| Field | Type | Constraints |
|---|---|---|
| id | UUID/String | Primary key |
| name | String | Required |
| source | String | Optional |
| file_name | String | Required |
| file_hash | String | Required, SHA-256 |
| row_count | Integer | Required |
| feature_count | Integer | Required |
| target_column | String | Required |
| validation_status | String | Required |
| created_at | DateTime | Required |

### 2.2 dataset_features

Stores feature metadata.

| Field | Type | Constraints |
|---|---|---|
| id | Integer | Primary key |
| dataset_id | UUID/String | Foreign key |
| feature_name | String | Required |
| data_type | String | Required |
| is_selected | Boolean | Required |
| missing_count | Integer | Default 0 |

### 2.3 experiments

Stores reproducible experiment configurations.

| Field | Type | Constraints |
|---|---|---|
| id | UUID/String | Primary key |
| name | String | Required |
| research_question | Text | Optional |
| dataset_id | UUID/String | Foreign key |
| model_type | String | Required |
| random_seed | Integer | Required |
| train_ratio | Float | Required |
| configuration_json | JSON/Text | Required |
| status | String | Required |
| created_at | DateTime | Required |

### 2.4 models

Stores trained model metadata.

| Field | Type | Constraints |
|---|---|---|
| id | UUID/String | Primary key |
| experiment_id | UUID/String | Foreign key |
| name | String | Required |
| version | String | Required |
| artifact_path | String | Required |
| preprocessing_path | String | Required |
| metrics_json | JSON/Text | Required |
| feature_schema_json | JSON/Text | Required |
| created_at | DateTime | Required |

### 2.5 predictions

Stores model outputs.

| Field | Type | Constraints |
|---|---|---|
| id | UUID/String | Primary key |
| model_id | UUID/String | Foreign key |
| input_hash | String | Required |
| predicted_class | String | Required |
| probabilities_json | JSON/Text | Optional |
| request_source | String | Required |
| created_at | DateTime | Required |

### 2.6 explanations

Stores explanation output.

| Field | Type | Constraints |
|---|---|---|
| id | UUID/String | Primary key |
| prediction_id | UUID/String | Foreign key |
| method | String | Required |
| top_features_json | JSON/Text | Required |
| base_value | Float | Optional |
| explanation_version | String | Required |
| created_at | DateTime | Required |

### 2.7 audit_records

Stores tamper-evident evidence.

| Field | Type | Constraints |
|---|---|---|
| id | UUID/String | Primary key |
| sequence_number | Integer | Required, unique |
| prediction_id | UUID/String | Foreign key |
| payload_json | JSON/Text | Required |
| previous_hash | String | Required |
| record_hash | String | Required |
| created_at | DateTime | Required |

## 3. SQLAlchemy-Style Models

```python
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer,
    String, Text, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str | None] = mapped_column(String(500))
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    target_column: Mapped[str] = mapped_column(String(255), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class ModelRecord(Base):
    __tablename__ = "models"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    experiment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiments.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(500), nullable=False)
    preprocessing_path: Mapped[str] = mapped_column(String(500), nullable=False)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    feature_schema_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class AuditRecord(Base):
    __tablename__ = "audit_records"
    __table_args__ = (
        UniqueConstraint("sequence_number"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    prediction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("predictions.id"), nullable=False
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
```

## 4. Pydantic API Schemas

```python
from datetime import datetime
from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    model_id: str
    features: dict[str, float | int | str]


class PredictionResponse(BaseModel):
    prediction_id: str
    predicted_class: str
    probabilities: dict[str, float] | None = None
    model_version: str
    created_at: datetime


class ExplanationResponse(BaseModel):
    prediction_id: str
    method: str
    top_features: list[dict]
    limitations: list[str]


class AuditVerificationResponse(BaseModel):
    verified: bool
    checked_records: int
    failed_records: list[str] = Field(default_factory=list)
    message: str
```

## 5. Hash-Linked Ledger Design

### Canonical payload

The payload must be serialized deterministically before hashing.

```json
{
  "prediction_id": "prediction-123",
  "predicted_class": "BENIGN",
  "model_version": "rf-v1",
  "explanation_summary": [
    {
      "feature": "flow_duration",
      "contribution": 0.31
    }
  ],
  "created_at": "2026-09-21T10:00:00Z"
}
```

### Hash calculation

```python
import hashlib
import json


def canonical_json(payload: dict) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def calculate_record_hash(
    payload: dict,
    previous_hash: str,
) -> str:
    material = previous_hash + canonical_json(payload)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
```

### Verification logic

1. Load records in sequence order.
2. Recompute each record hash.
3. Compare it with the stored hash.
4. Compare each record's previous hash with the preceding record hash.
5. Report all failures.
6. Do not silently repair records.

## 6. API Route Organization

```text
backend/
├── main.py
├── config.py
├── database.py
├── models/
│   ├── dataset.py
│   ├── experiment.py
│   ├── model.py
│   ├── prediction.py
│   ├── explanation.py
│   └── audit.py
├── schemas/
│   ├── dataset.py
│   ├── prediction.py
│   ├── explanation.py
│   └── audit.py
├── routes/
│   ├── datasets.py
│   ├── models.py
│   ├── predictions.py
│   ├── explanations.py
│   └── audit.py
└── services/
    ├── dataset_service.py
    ├── model_service.py
    ├── prediction_service.py
    ├── explanation_service.py
    └── audit_service.py
```

## 7. Schema Rules

- Never accept arbitrary model paths from API clients.
- Validate feature names against the stored model schema.
- Keep raw uploaded files outside the public frontend directory.
- Store hashes for uploaded datasets.
- Use UTC timestamps.
- Version model artifacts.
- Never overwrite an audit record in place.
- Record verification failures explicitly.
