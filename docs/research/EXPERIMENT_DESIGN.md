# SentinelCrypt AI — Experiment Design

## Overview

Four experiments investigate different aspects of trustworthy intrusion detection.
All experiments in the current implementation use **synthetic data** with controlled
properties. Real-dataset experiments (UNSW-NB15, CICIDS2017) are planned future work.

---

## A — Cross-Dataset Generalization (Synthetic)

### Research Question
How does model performance degrade under controlled distribution shift?

### Current Implementation (v1)
- **Source partition:** Synthetic network flows with `shift_scale=1.0`, `attack_ratio=0.3`
- **Target partition:** Synthetic network flows with `shift_scale=1.65`, `attack_ratio=0.35`
- **Distribution shift:** Achieved through exponential scaling of flow duration, Poisson rate multipliers, and shifted TTL distributions
- **Model:** RandomForestClassifier (n_estimators=50, max_depth=8, random_state=42)

### Common Feature Representation (Synthetic)
Both partitions share the same 10-dimensional feature space:
| Feature | Description | Type |
|---------|-------------|------|
| `dur` | Flow duration (seconds) | Numeric |
| `spkts` | Source-to-destination packet count | Numeric |
| `dpkts` | Destination-to-source packet count | Numeric |
| `sbytes` | Source-to-destination byte count | Numeric |
| `dbytes` | Destination-to-source byte count | Numeric |
| `rate` | Packet rate (packets/second) | Numeric |
| `sttl` | Source TTL value | Numeric |
| `dttl` | Destination TTL value | Numeric |
| `sload` | Source bits per second | Numeric |
| `dload` | Destination bits per second | Numeric |

### Leakage Prevention
- Train/test split: 70/30, stratified, random_state=42
- No target-dependent features used
- Preprocessing (not applied in synthetic experiments since features are already numeric)

### Planned Future Work (UNSW-NB15 ↔ CICIDS2017)
The real-dataset experiment requires:
1. **Feature mapping matrix** between UNSW-NB15 (49 features) and CICIDS2017 (78 features)
2. **Common feature subset** definition (features present in both datasets)
3. **Preprocessing compatibility** (different categorical/numeric distributions)
4. **Separate train/test splits** from each dataset to prevent leakage

### Metrics
- F1-Score (binary), Accuracy, Precision, Recall, ROC-AUC
- Generalization gap (ΔF1 = source_F1 - target_F1)

### Reproducibility
- `random_state`: 42 (source), 52 (target)
- `n_samples`: configurable (default 1200)
- Synthetic generation parameters are deterministic given the seed

---

## B — Explanation Stability

### Research Question
How stable are SHAP feature attributions under controlled Gaussian noise?

### Implementation
- **Model:** RandomForestDetector (n_estimators=30, max_depth=6, random_state=42)
- **Test sample:** First attack sample from synthetic dataset
- **Noise levels:** σ ∈ {0.01, 0.05, 0.10, 0.20}
- **Repetitions per level:** 8 (configurable)
- **Stability metric:** Cosine similarity between baseline and perturbed SHAP vectors

### Metrics
- Mean cosine similarity (stability score ∈ [0, 1])
- Standard deviation of per-repetition similarity
- Per-noise-level stability curve

### Limitations
- Stability measures consistency of model attribution, not causal correctness
- Only tested on tree-based models (TreeExplainer)
- Single test sample in current implementation

---

## C — Ledger Integrity & Tamper Detection

### Research Question
Can controlled modifications to the audit chain be detected?

### Implementation
- **Chain size:** 50 blocks (configurable)
- **Hash algorithm:** SHA-256 with RFC 8785 canonical JSON serialization
- **Genesis block:** 64 zero characters

### Tampering Scenarios Tested
1. **Payload mutation:** Feature/probability value changed in a single record
2. **Pointer modification:** `previous_hash` field rewritten with arbitrary bytes
3. **Record deletion:** Intermediate block removed (sequence gap)

### Metrics
- Detection status per attack type (boolean)
- Sequence number where detection occurs
- Chain build time (ms)
- Verification time per record (μs)
- Detection rate across tested scenarios

### Important Caveats
- Results are from **synthetic chains** with known structure
- "100% detection" means all 3 tested scenarios were caught on a chain of 50 blocks
- This does not guarantee detection of all possible tampering in production environments
- The ledger provides tamper **evidence**, not tamper **prevention**

---

## D — Model Comparison

### Research Question
How do linear vs non-linear models compare in accuracy and computational overhead?

### Implementation
- **Model 1:** LogisticRegression (max_iter=500, random_state=42)
- **Model 2:** RandomForestClassifier (n_estimators=50, max_depth=8, random_state=42)
- **Data:** Synthetic flow dataset (1500 samples, 75/25 split)
- **Cryptographic overhead:** Canonical JSON + SHA-256 measured over 500 iterations

### Metrics
- Accuracy, F1-Score, ROC-AUC
- Training time (ms)
- Inference time per sample (μs)
- Cryptographic overhead per prediction (μs)

---

## Reproducibility Protocol

Every experiment run records:
1. `random_state` / seed
2. `n_samples` and generation parameters
3. Model hyperparameters
4. Software versions (Python, scikit-learn, numpy, shap)
5. Timestamp
6. Experiment configuration as JSON

Results are stored in `results/` directory as deterministic JSON files.
