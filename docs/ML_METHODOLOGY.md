# Machine Learning Methodology — SentinelCrypt AI

## Overview

This document describes the ML evaluation strategy, class imbalance handling, and
metric selection rationale for the SentinelCrypt AI intrusion detection pipeline.

---

## 1. Class Imbalance Strategy

### The Problem

Network intrusion detection datasets are inherently imbalanced. In production
traffic, benign flows typically outnumber attack flows by 10:1 or more. A model
that always predicts "benign" can achieve 90%+ accuracy while detecting zero
attacks. Accuracy alone is therefore misleading as a performance metric.

### Current Approach: Natural Distribution Baseline

The current pipeline does **not** apply SMOTE, class weighting, undersampling,
or any other resampling technique. This is a deliberate baseline choice:

- **Why no resampling:** We want to measure how well the model learns from the
  natural class distribution. Resampling can mask generalization problems — a
  model that performs well on SMOTE-augmented training data may fail on real
  imbalanced traffic.
- **Why no class_weight='balanced':** Adding class weights changes the decision
  boundary. We want to establish an unbiased baseline before introducing
  controlled variables in future experiments.
- **Stratified splitting:** The train/test split preserves the original class
  ratios in both partitions, ensuring evaluation reflects real-world conditions.

### When to Add Imbalance Handling

Future experiments should evaluate these strategies as controlled variables:

| Strategy | When to try | Risk |
|---|---|---|
| `class_weight='balanced'` in RF/LR | When minority class recall is critically low | May increase false positives |
| SMOTE oversampling | When training data for attacks is very small | Can create unrealistic synthetic samples |
| Undersampling majority class | When dataset is large enough to lose samples | May discard useful information |
| Threshold tuning | When probability outputs are available | Requires a defined cost trade-off |

### Reporting Imbalance

Every evaluation automatically reports:
- `class_distribution.counts`: Raw sample count per class
- `class_distribution.proportions`: Fraction of total per class
- `class_distribution.is_imbalanced`: True if any class has < 10% of samples (binary)

---

## 2. Evaluation Metrics

### Primary Metrics (Always Reported)

| Metric | Formula | Why it matters for IDS |
|---|---|---|
| **F1-Macro** | Harmonic mean of precision and recall, averaged equally across classes | Does not reward ignoring the minority (attack) class. The single best summary metric under imbalance. |
| **Precision-Macro** | TP / (TP + FP) per class, averaged | High precision = few false alarms. Critical for analyst trust — too many false positives cause alert fatigue. |
| **Recall-Macro** | TP / (TP + FN) per class, averaged | High recall = few missed attacks. Critical for security — every missed attack is a potential breach. |

### Supplementary Metrics (When Probabilities Available)

| Metric | When to use | Limitation |
|---|---|---|
| **PR-AUC** | Best under class imbalance. Focuses on the minority (attack) class performance. | Threshold-dependent interpretation varies. |
| **ROC-AUC** | Threshold-independent measure of separability. | Can be optimistic when negative class dominates (high specificity inflates AUC). |
| **Brier Score** | Measures probability calibration (lower = better). | Requires reliable probability outputs. |

### Operational Metrics

| Metric | IDS interpretation |
|---|---|
| **False Positive Rate (FPR)** | Fraction of benign traffic flagged as attack. Directly causes alert fatigue. Target: < 1%. |
| **False Negative Rate (FNR)** | Fraction of attacks missed. Directly causes security gaps. Target: 0%. |
| **TP / TN / FP / FN counts** | Raw confusion matrix counts for absolute understanding. |

### Per-Class Metrics

`compute_detailed_report()` returns precision, recall, F1, and support for each
individual class. This is essential because:

- Aggregate metrics can hide poor performance on specific attack types.
- An IDS might have 95% overall recall but 50% recall on "Exploits" — the
  aggregate number would not reveal this critical gap.
- Different attack types have different severity and different detection
  difficulty.

---

## 3. When to Use Which Metric

| Scenario | Primary metric | Why |
|---|---|---|
| **Overall model comparison** | F1-Macro | Balanced view that doesn't ignore minority class |
| **Alert fatigue analysis** | FPR + Precision | Measures how many false alarms analysts must handle |
| **Detection coverage** | Recall-Macro + per-class recall | Shows which attack types are being missed |
| **Threshold selection** | PR-AUC | More informative than ROC-AUC under imbalance |
| **Probability quality** | Brier Score | Measures if predicted probabilities are well-calibrated |
| **Multi-class attacks** | Per-class F1 + confusion matrix | Shows which specific attack types need improvement |

### Accuracy caveat

Accuracy is reported for backward compatibility and simple sanity checks, but it
should **never** be the primary metric for IDS evaluation. A trivial "predict
all benign" baseline achieves accuracy = proportion of benign samples, which is
often 90%+ while detecting nothing.

---

## 4. Model Baselines

### Current Models

| Model | Type | Strengths | Weaknesses |
|---|---|---|---|
| **Logistic Regression** | Linear | Fast, interpretable coefficients, calibrated probabilities | Cannot capture non-linear feature interactions |
| **Random Forest** | Ensemble | Handles non-linearity, robust to outliers, feature importances | Slower inference, less interpretable individual predictions |

### Training Protocol

- **Split:** Stratified 80/20 train/test, `random_state=42`
- **Preprocessing:** Fit scalers and imputers on train only, transform test
- **Categorical encoding:** Label encoding fit on train, unseen test values → -1
- **Hyperparameters:** Sensible defaults (RF: 100 trees, max_depth=15; LR: L2, C=1.0)
- **No hyperparameter tuning:** Baselines use fixed defaults for reproducibility

### Evaluation Pipeline

1. Train on X_train, y_train
2. Predict on X_test
3. Compute all metrics (accuracy, precision, recall, F1, FPR, FNR, PR-AUC, ROC-AUC)
4. Generate confusion matrix and per-class report
5. Record class distribution for imbalance analysis
6. Persist results as JSON with reproducibility metadata

---

## 5. Future Work

- Controlled experiment: add `class_weight='balanced'` and measure impact on
  recall vs precision trade-off
- Threshold optimization using PR-AUC curve
- SMOTE-based augmentation experiment
- Multi-class evaluation on datasets with attack-type labels (UNSW-NB15 attack_cat)
- Cost-sensitive evaluation where different misclassification types have different penalties
