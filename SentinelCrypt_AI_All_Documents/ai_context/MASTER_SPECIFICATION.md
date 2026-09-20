# SentinelCrypt AI — Master Specification

**Version:** 1.0.0  
**Status:** Frozen implementation baseline  
**Purpose:** Single source of truth for human developers and AI coding agents.

## 1. Project Identity

SentinelCrypt AI is a defensive, research-oriented cybersecurity platform combining:
- ML-based network intrusion detection
- Explainable AI
- Tamper-evident cryptographic audit logging
- Reproducible research experiments

Research question:

> How does explanation reliability and cryptographic evidence verification contribute to the trustworthiness of ML-based network intrusion detection?

The project investigates three dimensions:
1. Detection performance
2. Explanation reliability
3. Evidence integrity

## 2. Scope

### MVP
- Public/authorized IDS datasets
- Dataset provenance and validation
- Reproducible preprocessing
- Logistic Regression
- Random Forest
- Precision, recall, F1, macro-F1, confusion matrix, PR-AUC where appropriate
- Prediction API
- SHAP explanations where technically appropriate
- Explanation-stability experiment
- Canonical audit evidence
- SHA-256 hash chaining
- Independent chain verification
- FastAPI backend
- React frontend
- SQLite
- Automated tests
- Reproducible experiments

### Out of scope for MVP
- Unauthorized network activity
- Credential theft
- Malware
- Evasion
- Live attacks
- Distributed blockchain consensus
- Cryptocurrency
- Production-SOC replacement claims
- Kubernetes
- Mandatory cloud deployment
- Mandatory authentication
- Microservices

All security testing must use public/authorized data or controlled local fixtures.

## 3. Approved Architecture

```text
React UI
   |
FastAPI API
   |
Service Layer
 |       |       |
ML      XAI    Crypto
Engine  Engine  Engine
 |       |       |
 +-------+-------+
         |
Repository Layer
         |
       SQLite
```

Research flow:

```text
Dataset -> Validation -> Preprocessing -> Training -> Evaluation
-> Prediction -> Explanation -> Evidence -> Hash Chain
-> Verification -> Dashboard -> Experiments
```

## 4. Repository Structure

```text
SentinelCrypt-AI/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── SECURITY.md
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── .gitignore
├── .env.example
├── pyproject.toml
├── requirements.txt
├── Makefile
├── .github/
│   ├── workflows/{ci.yml,security.yml,release.yml}
│   ├── ISSUE_TEMPLATE/{bug_report.md,feature_request.md,research_issue.md}
│   └── pull_request_template.md
├── docs/
│   ├── 00_PROJECT_CHARTER.md
│   ├── 01_PRODUCT_CONCEPT.md
│   ├── 02_PRD.md
│   ├── 03_SRS.md
│   ├── 04_SCOPE_USE_CASES_USER_STORIES.md
│   ├── 05_HLD_SYSTEM_ARCHITECTURE.md
│   ├── 06_LLD_DETAILED_DESIGN.md
│   ├── 07_DFD_UML_DESIGN.md
│   ├── 08_API_SPECIFICATION.md
│   ├── 09_DATABASE_SCHEMA.md
│   ├── 10_UI_UX_SPECIFICATION.md
│   ├── security/
│   ├── cryptography/
│   ├── ml/
│   ├── xai/
│   ├── research/
│   ├── ai/
│   ├── testing/
│   └── presentation/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── ml/
│   │   ├── xai/
│   │   ├── cryptography/
│   │   └── utils/
│   ├── migrations/
│   └── tests/
├── frontend/
│   ├── public/
│   ├── src/
│   └── tests/
├── data/{raw,processed,metadata}/
├── models/{trained,artifacts}/
├── experiments/
│   ├── EXP-A-cross-dataset/
│   ├── EXP-B-xai-stability/
│   ├── EXP-C-ledger-integrity/
│   └── EXP-D-model-comparison/
├── notebooks/
├── scripts/
├── results/{metrics,figures,tables,reports}/
├── artifacts/{demo,screenshots,presentation}/
└── config/
```

## 5. Backend Rules

API routes only validate requests, invoke services, and return schemas. They must not contain ML algorithms, cryptographic primitives, or raw persistence logic.

Services orchestrate workflows.

Repositories own database persistence.

ML code must be independent of HTTP/frontend concerns.

## 6. ML Specification

Initial models:
- Logistic Regression
- Random Forest

Every experiment records, where applicable:
- random seed
- dataset/version
- preprocessing configuration
- feature selection
- hyperparameters
- train/test strategy
- environment information

Prevent train/test leakage. Learned preprocessing must be fitted only on training data.

No fabricated metrics or manually entered results.

## 7. Dataset Provenance

Record:
- dataset name
- source
- retrieval date
- version
- license/usage terms
- local filename
- SHA-256 checksum
- rows/features
- label
- missing-value handling
- duplicate handling
- train/test strategy

Do not commit datasets unless redistribution is explicitly permitted.

## 8. XAI

SHAP is the initial explanation framework.

Store:
- model identifier
- prediction identifier
- feature names
- attribution values
- explanation metadata

Do not describe SHAP as causal proof.

Explanation reliability must document:
- perturbation strategy
- repetitions
- attribution representation
- similarity metric
- aggregation
- thresholds
- limitations

## 9. Cryptographic Audit

Purpose: provide tamper-evident evidence under an explicit trust/storage model.

Hash construction:

```text
canonical payload
      -> UTF-8 bytes
      -> previous_hash || payload_bytes
      -> SHA-256
      -> record_hash
```

Canonical serialization must be deterministic.

Verification checks:
1. record ordering
2. previous-hash linkage
3. current hash
4. required fields
5. chain continuity

This is NOT blockchain, distributed consensus, or proof that a prediction is true.

Conceptual audit record:

```text
id
timestamp
event_type
prediction_id
model_id
payload
previous_hash
record_hash
```

Do not store secrets in audit payloads.

## 10. API Contract

Base path: `/api/v1`

```text
GET    /health

POST   /datasets
GET    /datasets
GET    /datasets/{dataset_id}

POST   /models/train
GET    /models
GET    /models/{model_id}
GET    /models/{model_id}/metrics

POST   /predictions
POST   /predictions/batch
GET    /predictions/{prediction_id}

GET    /predictions/{prediction_id}/explanation

GET    /audit/records
GET    /audit/records/{record_id}
POST   /audit/verify

POST   /experiments
GET    /experiments
GET    /experiments/{experiment_id}
```

Use explicit request/response schemas.

## 11. Frontend

Required pages:
1. Dashboard
2. Datasets
3. Models
4. Predictions
5. Explainability
6. Audit Ledger
7. Experiments
8. Documentation
9. Settings

Dashboard should surface dataset/model counts, prediction activity, model metrics, ledger verification status, and experiment summaries.

## 12. Database

Core entities:
- datasets
- models
- predictions
- explanations
- audit_records
- experiments
- model_evaluations

Relationships:

```text
Dataset 1:N Model
Model 1:N Prediction
Prediction 1:0..1 Explanation
Prediction 1:1 AuditRecord
Experiment 1:N ModelEvaluation
```

Foreign keys, indexes, and deletion behavior must be explicit.

## 13. Testing

Required unit tests:
- preprocessing
- metrics
- model wrappers
- canonicalization
- hashing
- hash chain
- verification
- explanation logic

Required integration tests:
- dataset API
- training workflow
- prediction workflow
- explanation retrieval
- audit creation
- audit verification

Security tests:
- malformed input
- invalid IDs
- type validation
- changed payload
- changed previous hash
- changed record hash
- broken ordering
- missing fields

Golden path:

```text
dataset -> preprocess -> train -> predict -> explain -> audit -> verify
```

## 14. Experiments

### EXP-A — Cross-Dataset Generalization
Define dataset compatibility, mapping, preprocessing, training, evaluation, and limitations before execution.

### EXP-B — XAI Stability
Measure explanation consistency under controlled perturbations using a predefined metric and protocol.

### EXP-C — Ledger Integrity
Create valid local chain, verify it, mutate a controlled test record, verify again, and measure detection/verification overhead.

### EXP-D — Model Comparison
Compare approved models using the predefined methodology. Do not choose an arbitrary metric simply to produce a preferred result.

Every experiment contains:

```text
README.md
config.yaml
run.py
results/
```

## 15. Reproducibility

Record configuration, seeds, dataset identifiers, preprocessing, model parameters, and environment information where practical.

Distinguish:
- measured results
- derived values
- externally reported facts
- hypotheses

Never turn a hypothesis into a result.

## 16. AI Vibe-Coding Rules

The coding agent MUST:
- read this specification first
- inspect the repository before editing
- read relevant subsystem context
- make bounded changes
- preserve architecture
- use tests
- explain substantial architecture changes
- use deterministic audit serialization
- keep secrets out of source control

The agent MUST NOT:
- invent APIs/dependencies/datasets/citations/results
- remove tests to make code pass
- hardcode secrets
- silently redesign architecture
- add blockchain marketing claims
- claim SHAP is causal
- fabricate experiments
- add unnecessary microservices/Kubernetes
- rewrite unrelated files

## 17. Dependency Policy

Use a minimal dependency set.

Likely backend:
FastAPI, Uvicorn, Pydantic, SQLAlchemy, Alembic if needed, pandas, NumPy, scikit-learn, SHAP, joblib, pytest.

Likely frontend:
React, Vite, React Router, and one charting library if required.

Exact versions must be locked after compatibility testing.

## 18. Configuration and Secrets

Use configuration/environment variables for database URL, API settings, paths, logging, and experiment configuration.

`.env` is local only. `.env.example` contains placeholders.

Never commit secrets.

## 19. Logging and Errors

Do not log passwords, tokens, API keys, or unnecessary sensitive data.

API errors should be structured and should not expose stack traces in normal responses.

## 20. Git Strategy

Recommended commits:

```text
chore: initialize repository
docs: add master specification
docs: add architecture documentation
feat: add backend foundation
feat: add database layer
feat: add dataset ingestion
feat: add preprocessing pipeline
feat: add baseline models
feat: add evaluation engine
feat: add prediction service
feat: add cryptographic audit ledger
feat: add ledger verification
feat: add explanation service
feat: add research experiments
feat: add frontend foundation
feat: add research dashboard
test: add integrity regression tests
test: add API integration tests
experiment: add cross-dataset evaluation
experiment: add explanation stability analysis
docs: add research results
docs: finalize project report
```

## 21. MVP Definition of Done

- Dataset validation works
- Preprocessing works
- Logistic Regression works
- Random Forest works
- Evaluation is generated from actual runs
- Prediction endpoint works
- SHAP explanation works for supported cases
- Explanation-reliability protocol exists
- Audit records are generated
- SHA-256 chain works
- Valid chain verifies
- Controlled tampering is detected
- React dashboard consumes APIs
- Core tests pass
- Experiments are reproducible
- Dataset provenance is documented
- Documentation contains no unsupported claims
- README supports setup

## 22. Demo

```text
Dashboard
 -> dataset
 -> model metrics
 -> authorized test sample
 -> prediction
 -> explanation
 -> audit evidence
 -> verification
 -> controlled local tamper test
 -> failed verification
 -> research experiment results
 -> limitations/future work
```

## 23. Research Narrative

Present the system as an investigation into trustworthiness:

> SentinelCrypt AI investigates whether ML intrusion detection can be made more inspectable and auditable by jointly evaluating detection performance, explanation stability, and cryptographically verifiable evidence.

Do not claim the system solves trustworthy AI generally.

## 24. Final Priority

```text
Correctness
> Security
> Reproducibility
> Research validity
> Maintainability
> UI polish
> Feature count
```

A smaller experimentally defensible system is preferred to a larger system with unsupported claims.
