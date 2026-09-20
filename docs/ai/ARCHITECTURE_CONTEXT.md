# SentinelCrypt AI — Architecture Context

## Unidirectional Dependency Graph
```
React UI ──> FastAPI (API v1) ──> Services Layer ──> Repository Layer ──> Database (SQLite/PostgreSQL)
                                      │
               ┌──────────────────────┼──────────────────────┐
               ▼                      ▼                      ▼
           ML Engine              XAI Engine            Cryptography Engine
```

## Directory Responsibilities
- `backend/app/ml/`: Only machine learning models, preprocessing, metrics, and model registry. No web or DB imports.
- `backend/app/xai/`: Only SHAP explanations and reliability/stability computations.
- `backend/app/cryptography/`: Only canonical serialization, SHA-256 digests, hash chain linking, and integrity verification.
- `backend/app/services/`: Business workflow orchestrators (e.g., `PredictionService` orchestrates ML -> XAI -> Evidence -> Audit).
- `backend/app/api/`: FastAPI route handlers (HTTP validation, status codes, dependency injection).
- `backend/app/db/`: SQLAlchemy ORM models, session management, and CRUD repositories.
- `frontend/`: React 18 + Vite dashboard with dark-mode aesthetic and glassmorphism.
- `experiments/`: Standalone, reproducible experimental scripts (EXP-A to EXP-D).
- `notebooks/`: Exploratory notebooks only; production code belongs in `backend/app/`.
- `results/`: Isolated destination for generated tables, figures, metrics, and reports.
