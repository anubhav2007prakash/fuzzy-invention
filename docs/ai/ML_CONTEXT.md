# SentinelCrypt AI — Machine Learning Context

## Datasets Supported
- **UNSW-NB15:** Comprehensive modern network intrusion dataset covering 9 attack categories (Fuzzers, Analysis, Backdoors, DoS, Exploits, Generic, Reconnaissance, Shellcode, Worms).
- **CICIDS2017:** Out-of-distribution evaluation dataset for cross-dataset generalization experiments.

## Machine Learning Models
1. **Logistic Regression (Interpretable Baseline):**
   - L2 regularized, standard-scaled input features.
   - Fast linear decision boundaries.
   - Direct coefficient explainability + LinearSHAP.
2. **Random Forest (Non-linear Ensemble):**
   - Ensemble of 100 balanced decision trees (`n_estimators=100`, `max_depth=15`, `random_state=42`).
   - Handles multi-modal feature distributions and complex interactions.
   - TreeSHAP local and global attributions.

## Preprocessing Pipeline
- Handling missing / infinite values via median/mode imputation.
- One-Hot / Label encoding for categorical fields (`proto`, `service`, `state`).
- Standard / Robust scaling fitted strictly on training splits.
- Stratified train/test splitting (80/20 or 70/30) with fixed seed `42`.

## Evaluation Metrics
- **Accuracy, Precision, Recall, Specificity, F1-Score (Macro and Weighted)**
- **ROC-AUC & PR-AUC**
- **Brier Score (Probability Calibration)**
- **Confusion Matrix**
- **Inference Latency (ms/sample)**
