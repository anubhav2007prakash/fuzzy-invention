# Differential Testing — Specification & Verification Report

Implementation: `backend/tests/differential/` · Crypto reference oracle:
`backend/app/cryptography/reference/chain.py` · Run:
`pytest backend/tests/differential/ -v`

---

## 1. Introduction and Rationale

**Differential testing** compares two independent implementations of the same
specification and asserts that they agree on each fixed or generated test
input. A disagreement indicates a defect in at least one implementation or a
misunderstood specification and must fail the test for investigation.

This technique is particularly effective for SentinelCrypt because:

| Component | Why differential testing applies |
|---|---|
| **SHA-256 hashing** | The hash function is fully specified; a reference using only `hashlib` serves as an oracle |
| **Canonical JSON** | SentinelCrypt's documented sorted-key, compact JSON encoding is compared with a separately written recursive serializer |
| **Hash-chain construction** | `payload_hash = SHA-256(canonical(payload))` and `record_hash = SHA-256(prev+payload_hash)` — simple enough to re-implement from scratch |
| **Ledger verification** | The verification algorithm is documented step-by-step; a dict-based reference verifier is independent of the ORM layer |
| **Evaluation metrics** | Precision/recall/F1 have closed-form definitions; numpy arithmetic gives an exact reference |
| **Preprocessing pipeline** | Exact transformed arrays are compared with an independent implementation of the fixture's encoding, train-only imputation, and scaling rules |

### Critical Design Constraint

> **The production code and the reference implementation must not share
> implementation**.  If both call the same internal helper, a bug in that helper
> is invisible to the comparison.  Each reference is written from specification
> documents using only Python builtins, `hashlib`, or `numpy` arithmetic.

---

## 2. Framework Architecture

```
backend/tests/differential/
├── __init__.py                          Package exports
├── framework.py                         DifferentialHarness, DifferentialResult,
│                                        DifferentialSuiteReport
├── test_hashing_differential.py         DT-HASH-01 … DT-HASH-08
├── test_canonicalization_differential.py DT-CAN-01 … DT-CAN-12
├── test_hash_chain_differential.py      DT-CHAIN-01 … DT-CHAIN-08
├── test_verification_differential.py    DT-VER-01 … DT-VER-09
├── test_metrics_differential.py         DT-METR-01 … DT-METR-08
├── test_preprocessing_differential.py  DT-PREP-01 … DT-PREP-10
└── test_generated_differential.py       Seeded generated cases across all six components

backend/app/cryptography/reference/
├── __init__.py                          Aliases and verification result adapter
└── chain.py                             Shared reference oracle for crypto components
```

### Reference oracle locations

| Component | Reference location |
|---|---|
| Hashing | Inline in `test_hashing_differential.py` (`_ref_sha256`) |
| Canonicalization | `backend/app/cryptography/reference/chain.py` → `ref_canonical_json` |
| Hash-chain | `backend/app/cryptography/reference/chain.py` → `ref_payload_hash`, `ref_record_hash` |
| Verification | Inline in `test_verification_differential.py` (`_ref_verify`) |
| Metrics | Inline in `test_metrics_differential.py` (`_ref_metrics`) — numpy only |
| Preprocessing | `test_generated_differential.py::_reference_preprocess` — independent NumPy reference |

---

## 3. Component Coverage

### 3.1 Hashing — `test_hashing_differential.py`

**Production**: `backend.app.cryptography.hashing.sha256_hash`  
**Reference**: `_ref_sha256` — plain `hashlib.sha256().hexdigest()`

| Test ID | Description | Strategy |
|---|---|---|
| DT-HASH-01 | ASCII string inputs | Parametrized over 7 cases |
| DT-HASH-02 | Unicode / multibyte strings | Japanese, Arabic, Russian, emoji, Latin ext |
| DT-HASH-03 | Empty string | Includes NIST known-answer check |
| DT-HASH-04 | Raw bytes input | Null bytes, full byte range |
| DT-HASH-05 | Output format | Always 64-char lowercase hex |
| DT-HASH-06 | Determinism | 10 repetitions per input |
| DT-HASH-07 | Avalanche / single-bit sensitivity | 1-byte XOR flip |
| DT-HASH-08 | NIST known-answer test vectors | "abc", "", "abcdbcde…nopq" |

**Assertion**: `prod == ref` (exact string equality)

---

### 3.2 Canonicalization — `test_canonicalization_differential.py`

**Production**: `backend.app.cryptography.canonicalization.canonicalize`  
**Reference**: `backend.app.cryptography.reference.ref_canonical_json`

The reference independently implements SentinelCrypt's current serialization
contract via a **recursive descent serializer** instead of the production
`json.dumps(sort_keys=True)` call, so deviations in separators, key ordering,
float representation, or encoding are caught. This test suite does not claim
that Python's JSON serialization implements RFC 8785/JCS.

| Test ID | Description |
|---|---|
| DT-CAN-01 | Simple flat dicts with string values |
| DT-CAN-02 | Nested dicts and lists |
| DT-CAN-03 | Key ordering (lexicographic, recursive) |
| DT-CAN-04 | Float serialization (shortest round-trip) |
| DT-CAN-05 | `datetime` → ISO-8601 string (naive values treated as UTC; aware offsets preserved) |
| DT-CAN-06 | Empty dict `{}` and `{"items": []}` |
| DT-CAN-07 | Unicode keys and values |
| DT-CAN-08 | Boolean and `None` |
| DT-CAN-09 | Integer values (including `2**63`) |
| DT-CAN-10 | `NaN`/`Infinity` raises `ValueError` in both |
| DT-CAN-11 | Output is always valid JSON (`json.loads` succeeds) |
| DT-CAN-12 | Re-parsing is idempotent: `canon(loads(canon(x))) == canon(x)` |

**Assertion**: `prod == ref` (exact string equality)

---

### 3.3 Hash-Chain Construction — `test_hash_chain_differential.py`

**Production**: `backend.app.cryptography.hash_chain`  
**Reference**: `backend.app.cryptography.reference` (`ref_payload_hash`, `ref_record_hash`)

| Test ID | Description |
|---|---|
| DT-CHAIN-01 | Payload hash matches reference for 8 diverse payloads |
| DT-CHAIN-02 | Record hash `SHA-256(prev+payload_hash)` matches reference |
| DT-CHAIN-03 | Full triple `(canonical, payload_hash, record_hash)` from `build_audit_record_hashes` |
| DT-CHAIN-04 | `GENESIS_PREVIOUS_HASH == "0"*64` matches reference `GENESIS` |
| DT-CHAIN-05 | 5-record chain: production and reference agree link-by-link |
| DT-CHAIN-06 | Diverse payload types: floats, unicode, nested, datetime |
| DT-CHAIN-07 | Payload hash sensitivity: any field change changes hash |
| DT-CHAIN-08 | Record hash covers both `prev_hash` and `payload_hash` |

**Assertion**: exact hash string equality between production and reference

---

### 3.4 Verification — `test_verification_differential.py`

**Production**: `backend.app.cryptography.verifier.verify_ledger`  
**Reference**: `_ref_verify` — a plain-dict verifier that re-implements the four
verification steps independently of the ORM layer.

A `_MockRecord` adapter wraps plain dicts as ORM-like objects so the production
verifier can be called without a database.

| Test ID | Description | Expected outcome |
|---|---|---|
| DT-VER-01 | Empty ledger | `verified=True` in both |
| DT-VER-02 | Single honest record | `verified=True` in both |
| DT-VER-03 | 5-record honest chain | `verified=True` in both |
| DT-VER-04 | Payload silently mutated | `verified=False` in both |
| DT-VER-05 | Wrong `previous_hash` pointer | `verified=False` in both |
| DT-VER-06 | Wrong stored `record_hash` | `verified=False` in both |
| DT-VER-07 | Broken sequence (gap) | `verified=False` in production |
| DT-VER-08 | Out-of-order submission | `verified=True` in both (after sort) |
| DT-VER-09 | 50-record honest chain | `verified=True` in both |

**Assertion**: `production.verified == reference["verified"]`

---

### 3.5 Metrics — `test_metrics_differential.py`

**Production**: `backend.app.ml.evaluation.metrics.compute_metrics`  
**Reference**: `_ref_metrics` — numpy-only closed-form arithmetic for accuracy,
precision_macro, recall_macro, f1_macro (no sklearn).

**Scope limitation**: Probability-based metrics (ROC-AUC, PR-AUC, Brier score)
are not differentially tested because re-implementing ranking-based integrals
from scratch would be as complex as sklearn itself. These metrics are covered by
integration tests instead.

| Test ID | Description |
|---|---|
| DT-METR-01 | Perfect predictions → all metrics = 1.0 |
| DT-METR-02 | All wrong (inverted) → accuracy = 0.0 |
| DT-METR-03 | Random binary (5 seeds) — scalars match reference |
| DT-METR-04 | 3-class multiclass (3 seeds) — scalars match reference |
| DT-METR-05 | Imbalanced dataset — macro-F1 penalises majority classifier |
| DT-METR-06 | FPR and FNR match confusion-matrix arithmetic |
| DT-METR-07 | Determinism — 5 repetitions produce identical output |
| DT-METR-08 | Class distribution proportions sum to 1.0 |

**Assertion**: `abs(prod[metric] - ref[metric]) < 1e-9`

---

### 3.6 Preprocessing — `test_preprocessing_differential.py`

**Production**: `backend.app.ml.preprocessing.pipeline.build_preprocessing_pipeline`  
**Reference**: `test_generated_differential.py::_reference_preprocess`, which
manually encodes the controlled fixture, fits median imputation and scaling
statistics on training rows only, and applies those statistics to both splits.
The shared `train_test_split` call is intentional: it aligns the row selection
so that comparisons isolate preprocessing rather than compare split algorithms.

The existing preprocessing module also retains property checks. The generated
test compares `X_train`, `X_test`, `y_train`, and `y_test` element-wise against
the independent reference for seeded data, both supported scalers, missing and
infinite numeric values, and a category that may be absent from the training
split. Numeric comparisons use a tight tolerance to account for floating-point
implementation details. Failures include seed, scaler, output, maximum
absolute difference, and NumPy's index-level diagnostic.

## 3.7 Seeded generated cases — `test_generated_differential.py`

The generated cases use seed `20261001` for repeatability:

| Component | Generated cases |
|---|---|
| Canonical JSON | 250 recursively generated JSON-compatible objects |
| Hashing | 250 byte strings and 250 Unicode strings |
| Hash-chain construction | 200 generated payloads with independently generated prior digests |
| Verification | 40 valid shuffled ledgers and 40 corresponding payload-tampered ledgers |
| Metrics | 100 random binary/multiclass label and prediction arrays |
| Preprocessing | 5 seeds × 2 scalers (10 end-to-end numerical comparisons) |

---

## 4. Running the Tests

### Full differential suite

```bash
pytest backend/tests/differential/ -v --tb=short
```

### Single component

```bash
# Hashing only
pytest backend/tests/differential/test_hashing_differential.py -v

# Canonicalization only
pytest backend/tests/differential/test_canonicalization_differential.py -v

# Hash-chain only
pytest backend/tests/differential/test_hash_chain_differential.py -v

# Verification only
pytest backend/tests/differential/test_verification_differential.py -v

# Metrics only
pytest backend/tests/differential/test_metrics_differential.py -v

# Preprocessing only
pytest backend/tests/differential/test_preprocessing_differential.py -v

# Seeded generated cases for all six components
pytest backend/tests/differential/test_generated_differential.py -v
```

### With JSON report

```bash
pytest backend/tests/differential/ -v --tb=short \
  --json-report --json-report-file=results/differential-report.json
```

### Mismatch failure output

When a differential test fails, it reports both outputs:

```
FAILED test_canonicalization_differential.py::test_dt_can03_key_ordering
AssertionError: [DT-CAN-03] Canonicalization mismatch.
  production : '{"zebra":1,"apple":2}'
  reference  : '{"apple":2,"zebra":1}'
```

Generated-case failures additionally identify the deterministic seed and case.
The pytest assertion itself fails the suite; no report collector can turn a
mismatch into a passing test.

---

## 5. Test Count Summary

| Component | Generated cases | Comparisons per case |
|---|---:|---:|
| Hashing | 250 byte strings + 250 Unicode strings | 1 each |
| Canonicalization | 250 generated objects | 1 canonical string |
| Hash-chain | 200 generated payloads | Payload hash + record hash |
| Verification | 40 valid + 40 payload-tampered ledgers | Boolean result |
| Metrics | 100 generated datasets | 4 scalar metrics |
| Preprocessing | 5 seeds × 2 scalers | Train/test features + train/test labels |

These counts refer to deterministic generated inputs inside test functions,
not pytest test-item counts. Fixed and seeded parametrized cases remain
separate in their original modules. The seeded generator is reproducible; it
is not an exhaustive proof over all possible inputs.

---

## 6. Reference Implementation Design

### `backend/app/cryptography/reference/chain.py`

This file is the primary shared oracle for the cryptographic components.  Its
design principles:

1. **No production crypto helpers** — uses only `hashlib`, `json`, `math`, and
   `datetime`. Does not import production crypto helpers.
2. **Recursive descent** — `ref_canonical_json` builds canonical JSON via
   explicit recursive dispatch, not `json.dumps(sort_keys=True)`.  This means a
   regression in separator, encoding, or rounding in the production path is not
   masked by a shared code path.
3. **Test oracle only** — the file is annotated with `DO NOT IMPORT FROM
   PRODUCTION CODE`.  Importing it in production would defeat the purpose.
4. **Self-contained verification** — `ref_verify_chain` verifies a chain of
   plain dicts without touching the ORM, database, or any framework code.

### Inline references

For components where a shared-oracle file would be circular or inappropriate
(metrics, preprocessing), the reference is implemented **inline** in the test
module using Python counts or NumPy arithmetic. Generated preprocessing
comparisons share sklearn's deterministic train/test split only; encoding,
imputation, and scaling are computed independently. This keeps each test
module self-contained and independently readable.

---

## 7. Limitations and Out-of-Scope Items

| Item | Rationale |
|---|---|
| ROC-AUC, PR-AUC, Brier score | Re-implementing sorting-based integrals would be as complex as sklearn. Covered by integration tests. |
| XAI / explanation outputs | SHAP values are numerical approximations; their "correct" value is the SHAP algorithm, not an independent implementation. Covered by metamorphic testing. |
| Model predictions | ML model predictions depend on trained weights; there is no independent reference. Covered by metamorphic and property-based tests. |
| Database layer | ORM queries are not differentially testable without a running DB. Covered by integration tests. |

---

## 8. Adding New Differential Tests

To add a test for a new component:

1. Create `backend/tests/differential/test_<component>_differential.py`.
2. Implement a reference in the test file itself OR add to `reference/chain.py` if
   reusable across multiple test modules.
3. For each test ID (`DT-COMP-NN`), document:
   - What property is being compared
   - What the reference computes independently
   - The tolerance (exact for deterministic functions; `1e-9` for floats)
4. Update this document's test count table.

> [!IMPORTANT]
> The reference must **not** import from the production module it is testing.
> If you find yourself calling `sha256_hash` inside `_ref_sha256`, you have
> created a circular oracle that provides no protection.
