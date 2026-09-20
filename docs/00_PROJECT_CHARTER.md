# SentinelCrypt AI
## Product Concept Document (PCD)

**Version:** 1.0  
**Status:** Proposed research prototype  
**Owner:** Anubhav Prakash  
**Project Type:** Solo cybersecurity and machine-learning research project

---

## 1. Executive Summary

SentinelCrypt AI is a research-oriented network intrusion detection platform that combines:

1. Machine-learning-based network traffic classification.
2. Explainable AI for understanding model decisions.
3. Cryptographic, tamper-evident audit logging for security evidence.

The platform will allow a user to upload a supported network-flow dataset, train or load a model, classify traffic, inspect explanations, and verify the integrity of stored prediction records.

The product is intended for research, education, experimentation, and portfolio demonstration. It is not intended to replace a production Security Information and Event Management (SIEM) or an enterprise Intrusion Detection System (IDS).

## 2. Problem Statement

Traditional machine-learning intrusion detection demonstrations often focus primarily on classification accuracy. This creates three practical concerns:

- The model may perform poorly when traffic characteristics change.
- Analysts may not understand why an alert was generated.
- Stored alerts and explanations may be modified without an obvious integrity check.

SentinelCrypt AI addresses these concerns through a single, reproducible workflow.

## 3. Product Vision

Build a trustworthy and explainable ML-based network security research platform that helps students, researchers, and security learners investigate:

- Detection performance.
- Model generalization.
- Explanation reliability.
- Evidence integrity.

## 4. Target Users

### Primary users

- Cybersecurity and computer science students.
- Academic researchers.
- Faculty members supervising student research.
- ML engineers exploring security datasets.

### Secondary users

- Security analysts learning ML-based IDS.
- Developers building experimental security tooling.
- Internship reviewers evaluating technical portfolios.

## 5. Product Goals

### Must-have goals

- Provide a working network-flow classification pipeline.
- Support at least two ML models.
- Display precision, recall, F1-score, confusion matrix, and false-positive rate.
- Provide local explanations for predictions.
- Create a SHA-256 hash-linked audit ledger.
- Detect modified audit records.
- Expose functionality through a FastAPI backend.
- Provide a React dashboard.
- Include reproducible experiments and documentation.

### Research goals

- Compare model performance across datasets or controlled splits.
- Evaluate explanation stability and usefulness.
- Measure audit verification behavior and logging overhead.
- Identify limitations and possible future research directions.

### Non-goals

- Real-world offensive security operations.
- Automated exploitation.
- Malware generation.
- Live packet interception on third-party networks.
- Production-grade SOC replacement.
- Inventing a new cryptographic algorithm.
- Claiming that the prototype guarantees security.

## 6. Core User Journey

1. User opens the dashboard.
2. User selects a supported dataset.
3. System validates the dataset.
4. User trains or loads a model.
5. System displays evaluation metrics.
6. User selects a network-flow record.
7. System predicts the traffic class.
8. System generates an explanation.
9. System writes a tamper-evident audit record.
10. User verifies the audit chain.
11. User exports experiment results.

## 7. Product Modules

| Module | Purpose |
|---|---|
| Dataset Manager | Load, validate, inspect, and describe datasets |
| Preprocessing Pipeline | Clean and transform data without leakage |
| ML Engine | Train, save, load, and evaluate models |
| Prediction Engine | Classify individual or batch network flows |
| Explainability Engine | Generate local and global explanations |
| Audit Ledger | Store hash-linked prediction evidence |
| Verification Engine | Detect modified or broken records |
| Research Dashboard | Present results and system status |
| Experiment Manager | Record configurations and results |

## 8. Success Criteria

The prototype is successful when:

- A new user can run the system using documented instructions.
- A supported dataset can be processed reproducibly.
- At least two models can be compared.
- A prediction can be explained.
- A modified audit record is detected.
- The dashboard demonstrates the full workflow.
- The GitHub repository contains tests, documentation, and experiment results.

## 9. Product Risks

| Risk | Mitigation |
|---|---|
| Dataset leakage | Use pipeline-based preprocessing and leakage checks |
| Class imbalance | Report per-class metrics and balanced metrics |
| Weak generalization | Use held-out or cross-dataset evaluation |
| Misleading explanations | Report explanation limitations and stability tests |
| Ledger implementation errors | Use deterministic serialization and unit tests |
| Scope becoming too large | Prioritize P0 features |
| Unrealistic security claims | Clearly label the project as a research prototype |

## 10. Product Deliverables

- Working React dashboard.
- FastAPI backend.
- ML training and evaluation pipeline.
- Explainability module.
- Cryptographic audit ledger.
- Verification tests.
- Research notebooks.
- Architecture diagram.
- Technical documentation.
- Demonstration script.
- Research discussion document.
