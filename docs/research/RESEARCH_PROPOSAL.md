# SentinelCrypt AI — Research Proposal

## Title
**Trustworthy Network Intrusion Detection Through Explainable Predictions and Tamper-Evident Evidence**

## Abstract
This study examines trust-related properties of machine-learning intrusion detection beyond classification accuracy. A controlled prototype combines supervised IDS models, explainable AI, and a SHA-256 hash-linked audit ledger. Experiments examine model performance, cross-dataset generalization where compatible, explanation stability under controlled perturbations, and integrity verification behavior.

## Research Question
How do explanation reliability and cryptographic evidence verification contribute to the trustworthiness of ML-based network intrusion detection?

## Objectives
1. Establish reproducible IDS baselines.
2. Evaluate generalization where compatible.
3. Quantify explanation stability.
4. Measure ledger integrity detection and overhead.
5. Document limitations.

## Methodology
Dataset → preprocessing → baselines → evaluation → XAI → perturbation study → audit generation → mutation tests → overhead analysis.

## Expected Contribution
A reproducible prototype and measurable evaluation framework. Novelty must be established through literature review and evidence, not assumed from technology combination.

## Current Status (September 2026)

### Implemented and Measured
- Leakage-free ML preprocessing pipeline (fit on train only)
- Logistic Regression and Random Forest classifiers with comprehensive metrics
- SHAP-based local explanations with stability analysis
- SHA-256 hash chain audit ledger with canonical JSON serialization
- Tamper detection verified on synthetic chains (payload mutations, pointer modifications, record deletions)
- EXP-A, EXP-B, EXP-C, EXP-D executed on synthetic data partitions

### Planned / Future Work
- Cross-dataset evaluation on real UNSW-NB15 and CICIDS2017 datasets
- Feature mapping between different dataset schemas
- Larger-scale reproducibility studies
- Hardened deployment configuration

## Ethical Scope
Defensive, local, authorized experimentation only.
