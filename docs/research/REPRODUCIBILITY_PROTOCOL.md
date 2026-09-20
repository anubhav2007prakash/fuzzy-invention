# SentinelCrypt AI — Reproducibility Protocol

## 1. Random State & Determinism
- **Global Random Seed:** `42` across all NumPy, Python random, scikit-learn, and SHAP operations.
- **Environment Invariance:** Consistent float precision (6 decimal places in canonical payload formatting).

## 2. Leakage-Free Preprocessing Rules
1. Never call `.fit()` or `.fit_transform()` on test partitions.
2. Imputation statistics (medians, modes) and scaling statistics (means, standard deviations) are computed strictly from `X_train`.
3. Categorical encoding mappings are frozen on `X_train`; unseen test categories are mapped to an explicit `unknown` token or zero-vector.

## 3. Cryptographic Verification Standard
1. Payloads serialized using RFC 8785 JSON Canonicalization Scheme (JCS):
   - Sorted dictionary keys.
   - Minimal whitespace (`separators=(',', ':')`).
   - Standard UTF-8 encoding.
2. Standard SHA-256 generating 64-character lowercase hexadecimal strings.
3. Genesis block initialized with 64 zero characters: `0000000000000000000000000000000000000000000000000000000000000000`.

## 4. Benchmark Dataset Provenance & Integrity
- **UNSW-NB15:** SHA-256 checksums verified before ingestion.
- **CICIDS2017:** Pre-cleaned CSV splits with documented column mapping matrices.
