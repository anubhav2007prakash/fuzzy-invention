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
| **EXP-A** | Cross-Dataset Generalization | Train on UNSW-NB15, evaluate on CICIDS2017 to quantify out-of-distribution generalization drop. | F1-Score degradation ($\Delta F_1$), Recall, False Positive Rate (FPR). |
| **EXP-B** | Explanation Reliability & Stability | Evaluate SHAP attribution consistency across models and under controlled feature noise ($\epsilon \sim \mathcal{N}(0, \sigma^2)$). | Local Lipschitz continuity constant, Top-$k$ Jaccard similarity, Faithfulness. |
| **EXP-C** | Cryptographic Evidence Integrity | Benchmark SHA-256 hash chain verification runtime and validate 100% tamper detection rate under synthetic bit-flips. | Tamper detection rate ($100\%$), False positive rate ($0\%$), Verification latency vs $N$. |
| **EXP-D** | Model Comparison & Verification Trade-Offs | Compare interpretable linear models against non-linear tree ensembles on inference throughput vs. XAI compute overhead. | Accuracy, F1-Score, Inference Latency (ms), SHAP Compute Time (ms). |

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

### 4. Running Automated Tests
```bash
pytest backend/tests -v
```

---

## ⚖️ Scientific Rigor & Benchmark Disclaimer

- **Evaluation Protocol:** All preprocessing transformations (scalers, encoders, imputers) are fitted strictly on the training partition to eliminate data leakage.
- **Metrics Transparency:** We report macro/weighted Precision, Recall, F1-Score, False Positive Rate (FPR), and Confusion Matrices alongside Accuracy.
- **Cryptographic Scope:** The audit ledger uses an append-only cryptographic hash chain based on standard SHA-256 for tamper evidence. It is explicitly not a distributed blockchain.
- **Scope Limitation:** SentinelCrypt AI is an academic research prototype evaluated against benchmark datasets (UNSW-NB15, CICIDS2017) and does not constitute an enterprise-grade production security appliance.

---

## 📜 References & Literature
- **FRX-IDS:** Multiclass intrusion detection, explanations, validation diagnostics, and tamper-evident evidence logging (*ScienceDirect, 2026*).
- **TAE-IDS:** Trustworthy and explainable intrusion detection with ensemble learning and SHA-256 hash-linked audit records (*Frontiers, 2026*).
- **UNSW-NB15 Dataset:** Moustafa, N., & Slay, J. (2015). "UNSW-NB15: a comprehensive data set for network intrusion detection systems."
- **SHAP:** Lundberg, S. M., & Lee, S. I. (2017). "A unified approach to interpreting model predictions." *NeurIPS*.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
