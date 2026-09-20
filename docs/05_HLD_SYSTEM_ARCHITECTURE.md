# SentinelCrypt AI — System Architecture & High-Level Design

## Architecture
```text
React Research Dashboard
          |
       FastAPI
          |
  +-------+----------+------------+
  |       |          |            |
Dataset  ML      Prediction   Experiment
Manager Engine     Engine       Engine
  |       |          |            |
  +-------+----------+------------+
                    |
               Audit Ledger
                    |
                 SQLite
```

## Principles
Separation of concerns; deterministic processing; explicit provenance; least privilege; reproducibility; evidence-based security claims.

## Components
**Frontend:** research dashboard, metrics, predictions, explanations, ledger and experiments.

**API:** validation, routing, safe errors, local development interface.

**ML Engine:** preprocessing, training, evaluation, serialization.

**Prediction Engine:** schema validation, inference, confidence, explanation orchestration.

**Audit Ledger:** canonical serialization, hashing, persistence, verification.

**Experiment Engine:** configuration capture, execution, metrics, result storage.

## Trust Boundaries
Browser→API; API→database; API→model artifacts; experiment code→datasets; ledger writer→storage.

## Failure Isolation
An explanation failure must not silently change a prediction. An audit-write failure must be visible rather than treated as successful evidence.

## Deployment
Initial target: local Windows/WSL-compatible environment. Any remote/public deployment requires a separate security review.
