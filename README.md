# SentinelCrypt AI

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/frontend-React_18_%2B_Vite-61DAFB.svg)](https://react.dev/)
[![scikit-learn](https://img.shields.io/badge/ML-scikit--learn-F7931E.svg)](https://scikit-learn.org/)
[![SHAP](https://img.shields.io/badge/XAI-SHAP-FF6F00.svg)](https://shap.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **SentinelCrypt AI** is a research-oriented network intrusion detection platform that combines machine learning, explainable AI (XAI), and cryptographic evidence verification.
> 
> *Research prototype — not a production security product.*

---

## 🎯 Project Overview & Research Identity

Modern intrusion detection systems (IDS) can classify network traffic as benign or malicious, but three practical challenges persist in operational environments:
1. **Detection Reliability & External Generalization:** Models performing well on benchmark data often degrade significantly under out-of-distribution traffic.
2. **Explainability & Actionability:** Security analysts require interpretable, faithful rationales explaining why a high-priority alert was triggered.
3. **Evidence Integrity & Non-Repudiation:** Forensic alert records, model metadata, and explanations must remain tamper-evident and mathematically verifiable over time.

### Central Research Question
> *"How does explanation reliability and cryptographic evidence verification affect the trustworthiness of machine-learning-based network intrusion detection?"*

SentinelCrypt AI investigates this question by establishing a leakage-free ML pipeline, local and global SHAP explanations, a canonical SHA-256 forward-linked audit ledger, and a suite of four reproducible research experiments.

---

## 🏛 System Architecture

The architecture enforces strict unidirectional dependency layers:

```
                 ┌─────────────────────────────────────────┐
                 │       React 18 + Vite Dashboard         │
                 │   (Alerts • XAI Charts • Ledger Log)    │
                 └────────────────────┬────────────────────┘
                                      │  (HTTP / JSON REST)
                                      ▼
                 ┌─────────────────────────────────────────┐
                 │            FastAPI v1 API               │
                 └────────────────────┬────────────────────┘
                                      │  (Dependency Injection)
             ┌────────────────────────┼────────────────────────┐
             ▼                        ▼                        ▼
       ┌───────────┐            ┌───────────┐            ┌─────────────┐
       │ ML Engine │            │XAI Engine │            │Cryptography │
       │ (backend/ │            │ (backend/ │            │   Engine    │
       │  app/ml)  │            │  app/xai) │            │ (backend/   │
       └─────┬─────┘            └─────┬─────┘            │app/crypto)  │
             │                        │                  └──────┬──────┘
             └────────────────────────┼─────────────────────────┘
                                      ▼
                        ┌───────────────────────────┐
                        │     Services Layer        │
                        │   (backend/app/services)  │
                        └─────────────┬─────────────┘
                                      ▼
                        ┌───────────────────────────┐
                        │     Repository Layer      │
                        │ (backend/app/db/repos)    │
                        └─────────────┬─────────────┘
                                      ▼
                        ┌───────────────────────────┐
                        │  Relational Storage (ORM) │
                        │    (SQLite / Postgres)    │
                        └───────────────────────────┘
```

---

## 🔬 The Golden Path Research Pipeline

```
Network Flow Dataset (UNSW-NB15 / CICIDS2017)
   ↓
Schema & Type Validation (Checksum Verification)
   ↓
Leakage-Free Preprocessing (Fit strictly on Train Split)
   ↓
Stratified Train/Test Split (seed=42)
   ↓
Model Training (Logistic Regression & Random Forest)
   ↓
Comprehensive Evaluation (Precision, Recall, F1, FPR, ROC-AUC, PR-AUC)
   ↓
Real-Time / Batch Flow Prediction
   ↓
SHAP Feature Attribution (TreeSHAP / LinearSHAP)
   ↓
Explanation Reliability Assessment (Perturbation Sensitivity)
   ↓
Deterministic Evidence Generation (Canonical Payload)
   ↓
SHA-256 Evidence Digest Generation
   ↓
Cryptographic Hash Chain Forward Linkage
   ↓
Append-Only Audit Ledger Persistence
   ↓
Independent Verification & Tamper Detection
```

---

## 🧪 Research Experiments

| Experiment ID | Title | Research Focus | Primary Metrics |
|---|---|---|---|
| **EXP-A** | Cross-Dataset Generalization | Train on one synthetic partition, evaluate on a distribution-shifted partition to quantify generalization gap. | F1-Score degradation ($\Delta F_1$), Recall, False Positive Rate (FPR). |
| **EXP-B** | Explanation Reliability & Stability | Evaluate SHAP attribution consistency under controlled Gaussian feature noise. | Cosine similarity stability score, per-noise-level metrics. |
| **EXP-C** | Cryptographic Evidence Integrity | Benchmark SHA-256 hash chain verification and detect controlled tampering scenarios. | Detection of payload mutations, pointer modifications, and record deletions. |
| **EXP-D** | Model Comparison & Verification Trade-Offs | Compare Logistic Regression vs Random Forest on inference throughput and cryptographic overhead. | Accuracy, F1-Score, Inference Latency (ms), Cryptographic Overhead (μs). |

> **Important:** Experiment results reported below are from controlled synthetic benchmarks. Cross-dataset generalization (EXP-A) currently uses synthetic data partitions with distribution shift, not real UNSW-NB15/CICIDS2017 datasets. Tamper detection results (EXP-C) reflect the tested scenarios on a local chain and do not constitute a universal guarantee.

---

## 🛠 Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Language** | Python 3.10+ | Core backend runtime and scientific computing |
| **Machine Learning** | scikit-learn, pandas, NumPy | Preprocessing pipelines, LR and RF classifiers, metrics |
| **Explainability (XAI)** | SHAP (SHapley Additive exPlanations) | Local and global feature attribution vectors |
| **Cryptography** | Python hashlib (SHA-256), hmac, secrets | Canonical JSON serialization, forward hash chaining |
| **API Framework** | FastAPI, Pydantic v2 | High-performance asynchronous REST API |
| **Database** | SQLAlchemy 2.0 (SQLite / PostgreSQL) | Relational persistence of models, predictions, and audit ledger |
| **Frontend UI** | React 18, Vite, Recharts, Lucide Icons | Security analyst dashboard, XAI visualizer, ledger verifier |
| **Testing** | pytest, pytest-asyncio, httpx | Automated unit, integration, and security verification tests |

---

## 📦 Project Structure

```
SentinelCrypt-AI/
├── backend/                  # FastAPI backend, ML, XAI & Cryptography engines
│   ├── app/
│   │   ├── api/              # HTTP routers & dependency injection (API v1)
│   │   ├── core/             # Configuration, logging, exception handlers
│   │   ├── cryptography/     # Canonicalization, SHA-256 hash chain, verifier
│   │   ├── db/               # SQLAlchemy ORM models & repository layer
│   │   ├── ml/               # Leakage-safe preprocessing, LR & RF models, metrics
│   │   ├── schemas/          # Pydantic validation & response schemas
│   │   ├── services/         # Orchestration (Prediction, Training, Verification)
│   │   ├── utils/            # Hashing, serialization, UUID & timestamp helpers
│   │   └── xai/              # SHAP explainer, stability & fidelity evaluators
│   └── tests/                # Unit, integration, and ledger security tests
├── frontend/                 # React 18 + Vite web dashboard
│   └── src/
│       ├── api/              # REST API clients
│       ├── components/       # Charts (Recharts), tables, cards, layout
│       └── pages/            # Dashboard, Datasets, Models, Predictions, XAI, Audit
├── docs/                     # Comprehensive architecture and research documentation
│   ├── MASTER_SPECIFICATION.md # Central authoritative system blueprint
│   ├── ai/                   # AI agent and vibe coding context guidelines
│   ├── research/             # Literature review, experiment designs, BibTeX
│   └── presentation/         # Professor discussion sheets & demo scripts
├── experiments/              # Standalone runners for EXP-A, EXP-B, EXP-C, EXP-D
├── notebooks/                # Exploratory Jupyter analysis notebooks
├── scripts/                  # Project setup, dataset validation, evaluation scripts
└── results/                  # Generated figures, tables, and metrics reports
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ and npm

### 2. Backend Setup
```bash
# Clone and enter directory
git clone https://github.com/your-username/SentinelCrypt-AI.git
cd SentinelCrypt-AI

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests to verify installation
pytest backend/tests -v

# Launch FastAPI backend
uvicorn backend.app.main:app --reload --port 8000
```
Interactive API documentation will be available at: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
The React dashboard will be accessible at: [http://localhost:5173](http://localhost:5173)

### 4. Verify the Golden Path
```bash
# Upload a dataset via API
curl -X POST http://localhost:8000/api/v1/datasets \
  -F "file=@your_dataset.csv"

# Train a model
curl -X POST http://localhost:8000/api/v1/models/train \
  -H "Content-Type: application/json" \
  -d '{"dataset_id": "<id>", "model_type": "random_forest"}'

# Run a prediction
curl -X POST http://localhost:8000/api/v1/predictions \
  -H "Content-Type: application/json" \
  -d '{"model_id": "<id>", "features": {...}}'

# Verify the audit ledger
curl http://localhost:8000/api/v1/audit/verify
```

### 5. Running Automated Tests
```bash
pytest backend/tests -v  # Run all backend tests (unit + integration)
```

---

## ⚖️ Scientific Rigor & Benchmark Disclaimer

- **Evaluation Protocol:** All preprocessing transformations (scalers, encoders, imputers) are fitted strictly on the training partition to eliminate data leakage.
- **Metrics Transparency:** We report macro/weighted Precision, Recall, F1-Score, False Positive Rate (FPR), Confusion Matrices, and PR-AUC alongside Accuracy.
- **Cryptographic Scope:** The audit ledger uses an append-only cryptographic hash chain based on standard SHA-256 for tamper **evidence** (detection), not tamper **prevention**. It is explicitly not a distributed blockchain and does not provide consensus, immutability guarantees, or resistance to a compromised server administrator.
- **Scope Limitation:** SentinelCrypt AI is an academic research prototype. Current experiments use synthetic data with controlled distribution shifts. Cross-dataset generalization on real UNSW-NB15/CICIDS2017 datasets is planned future work.
- **Result Status:** Numbers reported in experiment results reflect the specific synthetic benchmarks executed. They should not be extrapolated to production network environments without further validation.

### What is implemented, measured, and planned
| Category | Status |
|---|---|
| ML pipeline with leakage-free preprocessing | ✅ Implemented |
| SHAP-based explanations with stability analysis | ✅ Implemented |
| SHA-256 hash chain audit ledger | ✅ Implemented |
| Tamper detection on synthetic chain | ✅ Measured (controlled scenarios) |
| Cross-dataset generalization (real datasets) | 🔲 Planned (future work) |
| Production-grade security hardening | 🔲 Planned |

---

## 🔒 Threat Model & Security Assumptions

### What the Cryptographic Ledger Protects Against
- **Payload tampering:** Any modification to stored evidence (features, predictions, timestamps) is detected because the SHA-256 hash chain would break.
- **Record deletion:** Removing or reordering records breaks the sequential hash chain linkage.
- **Pointer manipulation:** Changing the `previous_hash` field in any record breaks chain verification.
- **Retrospective alteration:** Modifying a past record invalidates all subsequent hashes in the chain.

### What the Ledger Does NOT Protect Against
- **Compromised server administrator:** A server admin with write access to the database can delete all records, modify the genesis hash, or rebuild the chain.
- **Pre-recording manipulation:** Data manipulated before being anchored into the ledger is not detectable.
- **Availability attacks:** The ledger provides integrity, not availability. An attacker who deletes the database destroys all evidence.
- **Consensus/distribution:** This is a single-server hash chain, not a distributed blockchain. There is no consensus protocol.
- **Side-channel attacks:** Timing, memory, or other side-channel attacks are not addressed.

### Assumptions
- The server operating system and Python runtime are trusted.
- The database file is backed up regularly (the ledger provides tamper evidence, not backup).
- API authentication is handled at the network level (not implemented in this prototype).
- Dataset files are validated before ingestion (schema + checksum verification).

---

## 📚 Dataset Acquisition

### Synthetic Data (Current Implementation)
All current experiments use procedurally generated synthetic network flow data with controlled distribution shifts. No external datasets are required to run the experiments.

### Planned: Real-World Datasets

#### UNSW-NB15
- **Source:** https://research.unsw.edu.au/projects/unsw-nb15-dataset
- **Version:** UNSW-NB15_1 (CSV files)
- **Expected structure:** 49 features + 2 label columns (`label`, `attack_cat`)
- **License:** Creative Commons Attribution 4.0 (CC BY 4.0)
- **Usage:** Train IDS models on diverse attack types including Fuzzers, Analysis, Backdoors, DoS, Exploits, Generic, Reconnaissance, Shellcode, and Worms.

#### CICIDS2017
- **Source:** https://www.unb.ca/cic/datasets/ids-2017.html
- **Version:** Wednesday working hours (Jun 21, 2017)
- **Expected structure:** 78 features + 1 label column (` Label`)
- **License:** CC BY 4.0 (Canadian Institute for Cybersecurity)
- **Usage:** Evaluate cross-dataset generalization against UNSW-NB15.

---

## 🔄 Research Reproducibility Instructions

To reproduce the experiments in this project:

```bash
# 1. Set up environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Run tests to verify installation
pytest backend/tests -v

# 3. Execute experiments (via API or scripts)
python scripts/run_experiment.py --experiment EXP-A
python scripts/run_experiment.py --experiment EXP-B
python scripts/run_experiment.py --experiment EXP-C
python scripts/run_experiment.py --experiment EXP-D

# 4. Results are stored in results/ as JSON files
ls results/
```

### Reproducibility Metadata
Every experiment result records:
- Random seed (42 for all experiments)
- Python and package versions (numpy, pandas, scikit-learn, shap)
- Platform information
- Timestamp
- Full experiment configuration as JSON

---

## 📜 References & Literature
- **FRX-IDS:** Multiclass intrusion detection, explanations, validation diagnostics, and tamper-evident evidence logging (*ScienceDirect, 2026*).
- **TAE-IDS:** Trustworthy and explainable intrusion detection with ensemble learning and SHA-256 hash-linked audit records (*Frontiers, 2026*).
- **UNSW-NB15 Dataset:** Moustafa, N., & Slay, J. (2015). "UNSW-NB15: a comprehensive data set for network intrusion detection systems."
- **SHAP:** Lundberg, S. M., & Lee, S. I. (2017). "A unified approach to interpreting model predictions." *NeurIPS*.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
