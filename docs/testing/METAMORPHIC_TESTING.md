# Metamorphic Testing Framework — Specification & Verification Report

Status: **COMPLETE** · Implementation: `backend/tests/metamorphic/` · CLI Harness: `scripts/metamorphic_harness.py` · Automated Test Suite: `backend/tests/unit/test_metamorphic.py` · Results: `results/metamorphic-report.json`

---

## 1. Executive Summary & Philosophy

In conventional software testing, test cases depend on an **oracle**—a mechanism that independently knows the exact expected output for any given input. In cybersecurity platforms combining machine learning, explainable AI, and cryptographic audit chains, test oracles are frequently unavailable:
- For arbitrary network flow inputs, what is the exact probability of intrusion?
- What are the ground-truth Shapley attributions for high-dimensional, correlated network flow telemetry?

**Metamorphic Testing (MT)** solves the test oracle problem. Instead of asserting absolute output values $f(x) = y$, MT identifies and asserts necessary **Metamorphic Relations (MRs)** between multiple system executions:
$$\text{If } x' = T(x), \text{ then } R(f(x), f(x')) \text{ must hold.}$$

### Critical Principle: No False Invariance Assumptions
> **Crucial Rule:** We do **NOT** assume that arbitrary input perturbations must preserve model predictions or explanations. In machine learning intrusion detection, arbitrary feature modifications (e.g. adding jitter or modifying feature values) *should* alter predictions if they cross the decision boundary. Assuming prediction invariance under arbitrary changes is an unsound testing anti-pattern.
>
> Every Metamorphic Relation in SentinelCrypt has a **strict mathematical, architectural, or cryptographic justification**.

---

## 2. Framework Architecture

The framework is implemented as an extensible, modular architecture:

```
backend/tests/metamorphic/
├── __init__.py                     # Package exports
├── framework.py                   # MetamorphicRelation, MetamorphicHarness, SuiteReport
├── fixtures.py                    # Reusable synthetic flows, trained detectors, honest chains
├── registry.py                    # Central catalog registering all 27 relations
├── preprocessing_relations.py     # MR-PRE-01 through MR-PRE-04
├── canonicalization_relations.py  # MR-CAN-01 through MR-CAN-04
├── hashing_relations.py           # MR-HASH-01 through MR-HASH-04
├── verification_relations.py      # MR-VER-01 through MR-VER-05
├── prediction_relations.py        # MR-PRED-01 through MR-PRED-05
└── explanation_relations.py       # MR-EXP-01 through MR-EXP-05

scripts/
└── metamorphic_harness.py         # Standalone CLI runner with filtering and JSON export

backend/tests/unit/
└── test_metamorphic.py            # Automated pytest suite integrating all relations
```

---

## 3. Metamorphic Relations Catalog

### Area 1: Preprocessing

#### MR-PRE-01: Metadata Field Dropping Invariance
* **Rationale:** In network flow analysis, raw captures contain metadata (source/destination IP addresses, ports, sequence numbers, packet arrival timestamps). SentinelCrypt's `pipeline.py` filters these out (`_DROP_PATTERNS`) to prevent shortcut learning and dataset leakage. Injecting, deleting, or altering metadata outside `feature_cols` must have zero effect on the transformed numerical feature vector.
* **Input Transformation:** Given a raw sample dictionary $x$, inject non-feature metadata keys ($x' = x \cup \{\text{srcip}: \text{"192.168.1.99"}, \text{dstip}: \text{"10.0.0.99"}, \text{timestamp}: 1727788800\}$).
* **Expected Property:** $T(x) == T(x')$ element-wise within $10^{-9}$ tolerance.
* **Test Implementation:** `preprocessing_relations.py::MR_PRE_01_MetadataInvariance` calls `transform_single_sample` on $x$ and $x'$ with a fitted pipeline and asserts `np.allclose(X_orig, X_pert, atol=1e-9)`.
* **Limitations:** Injected keys must strictly be outside the trained feature schema (`feature_cols`).

#### MR-PRE-02: Dictionary Key Insertion Order Invariance
* **Rationale:** A Python dictionary is an unordered key-value mapping. Feature mapping during preprocessing must strictly follow the model's frozen schema (`feature_cols`), completely independent of memory layout or key insertion order.
* **Input Transformation:** Construct $x'$ by reversing or randomly shuffling the key insertion order of dictionary $x$.
* **Expected Property:** $T(x) == T(x')$ element-wise.
* **Test Implementation:** `preprocessing_relations.py::MR_PRE_02_DictOrderInvariance` tests reversed and shuffled dictionary copies against original order.
* **Limitations:** Applies to dictionary representations; positional lists are ordered by definition.

#### MR-PRE-03: Out-of-Vocabulary Categorical Fallback Equivalence
* **Rationale:** When processing network traffic with novel protocol variants or unobserved service names, the pipeline maps unknown categories to the fallback index `-1` (via `_encode_categoricals`). Any two distinct out-of-vocabulary tokens for the same categorical field must produce the exact same encoded and scaled values.
* **Input Transformation:** Substitute an unseen categorical token $v_1$ (e.g. `'CUSTOM_PROTO_A'`) with another unseen categorical token $v_2$ (e.g. `'RESERVED_PROTO_B'`) for feature $c$.
* **Expected Property:** $T(x[c=v_1]) == T(x[c=v_2])$ element-wise.
* **Test Implementation:** `preprocessing_relations.py::MR_PRE_03_UnseenCategoricalEquivalence` transforms two samples with different novel tokens and asserts array equality.
* **Limitations:** Both categorical tokens must be completely absent from the training vocabulary of the categorical encoder.

#### MR-PRE-04: Batch Inference Isolation / Stateless Preprocessing
* **Rationale:** In production, inference samples arrive individually (API) or in bulk (batch). Because preprocessing at test time uses frozen parameters (training median, scaling centers), transforming a sample individually must yield the identical vector as transforming it surrounded by arbitrary other samples in a batch. No inter-sample cross-talk may exist.
* **Input Transformation:** Given target sample $x_i$ and companion samples $x_1, x_2$, transform $x_i$ via `transform_single_sample(x_i)` versus as part of batch $[x_1, x_i, x_2]$ via `transform_batch_samples`.
* **Expected Property:** $T_{single}(x_i) == T_{batch}(X)[1]$ within $10^{-9}$ tolerance.
* **Test Implementation:** `preprocessing_relations.py::MR_PRE_04_BatchIsolationConsistency` verifies that `X_single == X_batch[1:2]`.
* **Limitations:** Requires the exact same serialized pipeline artifact for both calls.

---

### Area 2: Canonicalization

#### MR-CAN-01: Key Permutation Invariance (RFC 8785 Lexicographic Sorting)
* **Rationale:** In JSON, objects represent unordered sets of key-value pairs. To generate reproducible cryptographic evidence digests across different programming languages and runtimes, RFC 8785 canonicalization recursively sorts dictionary keys lexicographically. Permuting key insertion order at any level must yield the exact same canonical byte stream.
* **Input Transformation:** Recursively permute (reverse or randomize) the key insertion order of dictionary $P$ to form $P'$.
* **Expected Property:** $\text{canonicalize}(P) == \text{canonicalize}(P')$ and $\text{SHA256}(\text{canonicalize}(P)) == \text{SHA256}(\text{canonicalize}(P'))$.
* **Test Implementation:** `canonicalization_relations.py::MR_CAN_01_KeyShufflingInvariance` constructs deeply nested dictionaries, reverses and shuffles keys at all levels, and asserts identical canonical strings and digests.
* **Limitations:** Applies to dictionary keys; JSON array elements have semantic order.

#### MR-CAN-02: Insignificant Whitespace Normalization
* **Rationale:** JSON payloads transmitted over HTTP networks or saved to log files often have varying indentation, spaces around colons/commas, or trailing newlines. Canonicalization eliminates all insignificant whitespace (`separators=(',', ':')`). Any formatting variation of the same logical data must serialize to the same canonical representation.
* **Input Transformation:** Format a source payload as minified, pretty-printed (`indent=4`), and tab-spaced JSON strings.
* **Expected Property:** $\text{canonicalize}(\text{json.loads}(J_{min})) == \text{canonicalize}(\text{json.loads}(J_{pretty})) == \text{canonicalize}(\text{json.loads}(J_{spaced}))$.
* **Test Implementation:** `canonicalization_relations.py::MR_CAN_02_WhitespaceNormalization` loads JSON from minified string, pretty string, and extra-space string, asserting all canonicalize identically.
* **Limitations:** Whitespace inside string literal values is preserved.

#### MR-CAN-03: ISO-8601 UTC Datetime Normalization
* **Rationale:** Audit log timestamps represent physical points in time. `canonical_serializer` converts naive and offset-aware datetimes to UTC. Two datetime instances representing the exact same physical instant (e.g. UTC vs UTC+05:30) must serialize to the identical ISO-8601 string, preventing false ledger integrity rejections across timezones.
* **Input Transformation:** Substitute a UTC datetime $dt_{utc}$ with an equivalent timezone-shifted datetime $dt_{offset}$ representing the identical instant in time.
* **Expected Property:** $\text{canonicalize}(\{\text{"timestamp"}: dt_{utc}\}) == \text{canonicalize}(\{\text{"timestamp"}: dt_{offset}.\text{astimezone}(\text{timezone.utc})\})$.
* **Test Implementation:** `canonicalization_relations.py::MR_CAN_03_TimezoneUTCNormalization` compares UTC instant with equivalent IST instant.
* **Limitations:** Both datetime objects must correspond to the identical physical instant.

#### MR-CAN-04: Non-Finite Float Rejection Invariance
* **Rationale:** RFC 8785 explicitly forbids `NaN` and `Infinity` in JSON. Emitting non-standard tokens causes unresolvable digest divergence across non-Python clients. SentinelCrypt's canonicalizer enforces this by raising `ValueError`. Injecting `NaN` or `Inf` into any field must deterministically trigger rejection.
* **Input Transformation:** Inject `float('nan')` or `float('inf')` into an otherwise serializable payload.
* **Expected Property:** $\text{canonicalize}(P_{valid})$ succeeds, while $\text{canonicalize}(P_{nan})$ strictly raises `ValueError`.
* **Test Implementation:** `canonicalization_relations.py::MR_CAN_04_NonFiniteFloatRejection` verifies that valid floats serialize and non-finite floats raise `ValueError`.
* **Limitations:** Applies specifically to non-finite floating point numbers.

---

### Area 3: Cryptographic Hashing

#### MR-HASH-01: Avalanche and Preimage Sensitivity
* **Rationale:** SHA-256 guarantees preimage resistance and the avalanche effect: changing a single input bit flips approximately 50% (128) of the output bits in an unpredictable manner. Any single-character edit to an audit payload must yield a completely distinct digest with high bit-level Hamming distance.
* **Input Transformation:** Alter a single character in the payload (e.g. increment an integer from 100 to 101).
* **Expected Property:** $H(P) \ne H(P')$ and $\text{HammingDistance}(H(P), H(P')) \ge 64$ bits (out of 256).
* **Test Implementation:** `hashing_relations.py::MR_HASH_01_PreimageSensitivity` computes SHA-256 for $P$ and $P'$, asserts inequality, and measures bit-level Hamming distance.
* **Limitations:** Holds cryptographically with probability $1 - 2^{-256}$.

#### MR-HASH-02: Hash Chain Operand Non-Commutativity
* **Rationale:** In SentinelCrypt's hash chain, `calculate_record_hash(prev_hash, payload_hash)` evaluates $\text{SHA-256}(prev\_hash + payload\_hash)$. String concatenation is non-commutative. Swapping the operands must produce a completely different record hash to prevent prefix-suffix interchange attacks.
* **Input Transformation:** Evaluate $\text{calculate\_record\_hash}(H_{prev}, H_{payload})$ versus $\text{calculate\_record\_hash}(H_{payload}, H_{prev})$.
* **Expected Property:** $\text{calculate\_record\_hash}(A, B) \ne \text{calculate\_record\_hash}(B, A)$ when $A \ne B$.
* **Test Implementation:** `hashing_relations.py::MR_HASH_02_ChainOperandNonCommutativity` calls `calculate_record_hash` in both directions and asserts strict inequality.
* **Limitations:** Requires $A \ne B$.

#### MR-HASH-03: Merkle Tree Domain Separation (Leaf vs Node Invariance)
* **Rationale:** To prevent second-preimage attacks where an interior node hash is misinterpreted as a leaf payload, Merkle trees prepend distinct 1-byte domain separation prefixes: `0x01` for leaves (`leaf_hash`) and `0x00` for interior nodes (`node_hash`). For any two child hashes $l$ and $r$, `leaf_hash(l + r)` must NEVER equal `node_hash(l, r)`.
* **Input Transformation:** Given two 32-byte digests $l$ and $r$, compute `leaf_hash(l + r)` and `node_hash(l, r)`.
* **Expected Property:** $\text{leaf\_hash}(l + r) \ne \text{node\_hash}(l, r)$.
* **Test Implementation:** `hashing_relations.py::MR_HASH_03_MerkleDomainSeparation` evaluates leaf and node prefixes over identical concatenation.
* **Limitations:** $l$ and $r$ must each be 32 bytes.

#### MR-HASH-04: Merkle Odd-Leaf Duplication Structural Invariance
* **Rationale:** SentinelCrypt's `MerkleTree` follows the Bitcoin/RFC convention for odd leaf counts: if a level has an odd number of nodes, the last node is duplicated. Therefore, a tree built from leaves $[l_1, l_2, l_3]$ must have the exact same root hash as a tree built from $[l_1, l_2, l_3, l_3]$.
* **Input Transformation:** Given odd leaf sequence $L = [l_1, l_2, l_3]$, construct $L' = [l_1, l_2, l_3, l_3]$.
* **Expected Property:** $\text{MerkleTree}(L).\text{root} == \text{MerkleTree}(L').\text{root}$.
* **Test Implementation:** `hashing_relations.py::MR_HASH_04_MerkleOddLeafDuplication` builds trees with 3 and 4 leaves and asserts root identity.
* **Limitations:** Applies specifically when the initial leaf count is odd.

---

### Area 4: Evidence Verification

#### MR-VER-01: Inductive Chain Extension Invariance
* **Rationale:** A forward-linked cryptographic hash chain is an append-only inductive log. If a ledger of length $k$ is authentic and verifies against genesis, appending a newly constructed valid record $k+1$ (whose `previous_hash` links to record $k$'s `record_hash`) must preserve validity across all $k+1$ records without altering historical verification status.
* **Input Transformation:** Given authentic ledger $L$ of length $k$, append a newly minted honest record $R_{k+1}$.
* **Expected Property:** $\text{verify\_ledger}(L).\text{verified} == \text{True} \implies \text{verify\_ledger}(L \cup [R_{k+1}]).\text{verified} == \text{True}$ and $\text{checked\_count} == k + 1$.
* **Test Implementation:** `verification_relations.py::MR_VER_01_InductiveExtensionInvariance` creates an honest 4-record chain, appends a 5th valid record, and asserts full verification.
* **Limitations:** The appended record must be honestly constructed according to chain protocol.

#### MR-VER-02: Monotonic Tamper Sensitivity (Single Record Corruption)
* **Rationale:** The core guarantee of SentinelCrypt's evidence ledger is tamper detection. Mutating any record's stored payload string (e.g. modifying class prediction or alert telemetry) without updating its hash must cause `verify_ledger` to fail and pinpoint the compromised record sequence number.
* **Input Transformation:** In an authentic chain $L$, modify the `payload_json` of record $i$ (e.g. $i=2$).
* **Expected Property:** $\text{verify\_ledger}(L').\text{verified} == \text{False}$, $\text{tamper\_detected} == \text{True}$, and `failed_records` flags sequence number $i$.
* **Test Implementation:** `verification_relations.py::MR_VER_02_SingleRecordTamperSensitivity` mutates payload of record 2 in a 4-record chain, asserting detection.
* **Limitations:** Assumes attacker does not forge a complete valid chain from genesis.

#### MR-VER-03: Prefix Validity Under Truncation
* **Rationale:** Any historical prefix of an authentic forward-linked ledger starting at genesis ($L_{1..m}$ for $1 \le m < k$) is mathematically a complete and valid audit ledger. Verification must succeed for any initial checkpoint.
* **Input Transformation:** Given authentic ledger of length $k=5$, construct truncated prefixes of length 1, 2, 3, 4.
* **Expected Property:** For all $m \in [1..k]$, $\text{verify\_ledger}(L_{1..m}).\text{verified} == \text{True}$.
* **Test Implementation:** `verification_relations.py::MR_VER_03_PrefixValidityUnderTruncation` slices prefixes of length 1 through 4 and asserts verification.
* **Limitations:** The sub-chain must be a prefix starting from sequence 1.

#### MR-VER-04: Non-Genesis Suffix Rejection (Genesis Anchor Invariance)
* **Rationale:** The audit ledger requires that sequence number 1 links to `GENESIS_PREVIOUS_HASH`. An adversary cannot take an arbitrary middle section of an authentic ledger (e.g. records 2..4) and claim it is a complete valid audit trail. Verification must reject such suffixes due to sequence or genesis pointer mismatch.
* **Input Transformation:** Drop record 1 from authentic ledger $L$ to evaluate suffix $L_{2..k}$.
* **Expected Property:** $\text{verify\_ledger}(L_{2..k}).\text{verified} == \text{False}$.
* **Test Implementation:** `verification_relations.py::MR_VER_04_NonGenesisSuffixRejection` passes suffix `chain[1:]` (records 2..4) to `verify_ledger`, asserting rejection.
* **Limitations:** Requires authentic chain length $k \ge 2$.

#### MR-VER-05: Notary Artifact Payload-Digest Entanglement
* **Rationale:** In SentinelCrypt's research notary service, an artifact contains an Ed25519 signature over the SHA-256 digest of canonicalized payload. Modifying any field in the payload without re-signing breaks digest matching and signature verification.
* **Input Transformation:** Sign honest payload $P$ with `sign_result` to produce artifact $A$. Modify a value in $A[\text{'payload'}]$.
* **Expected Property:** $\text{verify\_artifact}(A').\text{valid} == \text{False}$ and $\text{digest\_match} == \text{False}$.
* **Test Implementation:** `verification_relations.py::MR_VER_05_NotaryPayloadDigestEntanglement` alters an accuracy metric in a signed payload, asserting verification failure.
* **Limitations:** Private key is not available to the adversary to sign the altered payload.

---

### Area 5: Prediction Behavior

#### MR-PRED-01: Metadata Field Invariance for Model Inference
* **Rationale:** In SentinelCrypt, network intrusion detectors are strictly trained on statistical flow features. Flow headers and identifiers (IP addresses, timestamps, ports) are pruned during preprocessing. Injecting or altering these non-feature metadata fields must have zero influence on feature transformation, predicted class, and probability distribution.
* **Input Transformation:** Given raw input dictionary $x$, inject non-feature metadata fields (`srcip`, `dstip`, `timestamp`, `sensor_id`) to form $x'$.
* **Expected Property:** $\text{predicted\_class}(x') == \text{predicted\_class}(x)$ and $\max |\Delta P(x)| < 10^{-6}$.
* **Test Implementation:** `prediction_relations.py::MR_PRED_01_MetadataInvariance` transforms $x$ and $x'$ through the fitted pipeline, predicts with the trained detector, and asserts class and probability vector equality.
* **Limitations:** Injected keys must not overlap with trained model feature columns.

#### MR-PRED-02: Input Feature Key Ordering Invariance
* **Rationale:** Dictionaries represent unordered key-value mappings. When inference requests arrive with keys in arbitrary order, the prediction service extracts features by column name and hashes the canonicalized input. Reordering keys must result in identical predictions, identical probabilities, and identical canonical input hashes.
* **Input Transformation:** Reverse and shuffle the key insertion order of feature dictionary $x$ to form $x'$.
* **Expected Property:** $\text{predicted\_class}(x') == \text{predicted\_class}(x)$, $\text{probabilities}(x') == \text{probabilities}(x)$, and $\text{SHA256}(\text{canonicalize}(x')) == \text{SHA256}(\text{canonicalize}(x))$.
* **Test Implementation:** `prediction_relations.py::MR_PRED_02_KeyOrderInvariance` tests prediction and hashing across key orderings.
* **Limitations:** The key-value pairs themselves must be identical.

#### MR-PRED-03: Directional Monotonicity Under Attack-Indicator Amplification
* **Rationale:** For a linear model $f(x) = \sigma(w^T x + b)$, the decision boundary logit is strictly monotonic with respect to each feature $j$ according to the sign of its weight $w_j$. If a feature $j$ has a positive weight $w_j > 0$ for class 1 (ATTACK), increasing $x_j$ by $\Delta > 0$ while holding all other features fixed strictly increases the logit. Because the logistic sigmoid is strictly increasing, $P(\text{ATTACK} \mid x') \ge P(\text{ATTACK} \mid x)$. Furthermore, if $x$ is already classified as ATTACK (prob > 0.5), $x'$ cannot flip to BENIGN.
* **Input Transformation:** In a fitted Logistic Regression detector, locate feature $j$ with positive weight $w_j > 0$. Increase $x_j$ by $\Delta > 0$.
* **Expected Property:** $P(\text{ATTACK} \mid x') \ge P(\text{ATTACK} \mid x) - 10^{-9}$. If $\text{pred}(x) == 1$, then $\text{pred}(x') == 1$.
* **Test Implementation:** `prediction_relations.py::MR_PRED_03_PositiveWeightFeatureMonotonicity` finds positive-weight feature $j$, evaluates increments $\Delta \in [1.0, 2.5, 5.0]$, and asserts monotonic non-decrease of $P(\text{ATTACK})$.
* **Limitations:** Applies to linear decision boundaries where the weight sign is strictly positive.

#### MR-PRED-04: Batch Row Isolation and Permutation Invariance
* **Rationale:** Network intrusion detection systems operate on streams and micro-batches. A detector must evaluate each flow independently: sample $x$ must receive the identical prediction whether processed singly, surrounded by other benign flows, or surrounded by attack flows in a batch.
* **Input Transformation:** Evaluate sample $x$ individually, then within batch $[x_{benign}, x, x_{attack}]$, then in permuted batch $[x, x_{attack}, x_{benign}]$.
* **Expected Property:** $\text{pred}(x) == \text{pred}_{batch1}[1] == \text{pred}_{batch2}[0]$ and probabilities match within $10^{-6}$.
* **Test Implementation:** `prediction_relations.py::MR_PRED_04_BatchRowIsolation` runs single and multi-batch inferences with different neighbor arrangements and asserts row isolation.
* **Limitations:** Model must be stateless across inference calls.

#### MR-PRED-05: Confidence Threshold Monotonic Uncertainty
* **Rationale:** SentinelCrypt's prediction service tags samples as `'UNCERTAIN'` whenever $\max_c P(c \mid x) < \text{threshold}$. Because the condition $\max P < \theta$ is monotonic with respect to $\theta$, increasing the threshold from $\theta_1$ to $\theta_2$ ($\theta_2 > \theta_1$) can only expand the rejection region. Any sample uncertain under $\theta_1$ MUST strictly remain uncertain under $\theta_2$.
* **Input Transformation:** For a sample with maximum predicted probability $p$, evaluate confidence thresholding at $\theta_1$ and $\theta_2$ where $\theta_1 < \theta_2$.
* **Expected Property:** $\text{If is\_uncertain}(x, \theta_1) == \text{True}$, then $\text{is\_uncertain}(x, \theta_2) == \text{True}$.
* **Test Implementation:** `prediction_relations.py::MR_PRED_05_ConfidenceThresholdMonotonicity` evaluates rejection monotonicity across thresholds.
* **Limitations:** Valid for thresholds $\theta \in [0, 1]$.

---

### Area 6: Explanation Behavior

#### MR-EXP-01: Shapley Null Player Axiom (Zero-Weight Feature Invariance)
* **Rationale:** The Null Player axiom of cooperative game theory requires that if a feature has zero marginal contribution across all coalitions (e.g. weight $w_j = 0$ in a linear model), its Shapley value must be exactly zero: $\phi_j(x) = 0$. Furthermore, modifying the value of this dummy feature must not alter its own attribution or distort the attributions of any other features.
* **Input Transformation:** In a linear detector where feature $j$ has coefficient $0.0$, shift $x_j$ to $x_j + \Delta$.
* **Expected Property:** $\phi_j(x) == 0.0$, $\phi_j(x') == 0.0$, and $|\phi_k(x') - \phi_k(x)| < 10^{-5}$ for all $k \ne j$.
* **Test Implementation:** `explanation_relations.py::MR_EXP_01_NullFeatureZeroAttribution` sets feature 5 coefficient to 0.0, shifts feature 5 by 100.0, and asserts zero attribution and invariant attributions for other features.
* **Limitations:** Requires a feature with zero weight in a linear model.

#### MR-EXP-02: Shapley Efficiency Axiom (Completeness Invariance)
* **Rationale:** The efficiency (completeness) axiom guarantees that the sum of all feature SHAP attributions plus the baseline expected value equals the model's raw decision function output: $\sum_{i=1}^M \phi_i(x) + \text{base\_value} = f(x)$. This relationship must hold identically for any input $x$ and any transformed input $x'$.
* **Input Transformation:** Transform input $x$ to $x'$ by perturbing multiple continuous features.
* **Expected Property:** $|\sum \phi_i(x) + \text{base\_value} - f(x)| < 10^{-4}$ and $|\sum \phi_i(x') + \text{base\_value} - f(x')| < 10^{-4}$.
* **Test Implementation:** `explanation_relations.py::MR_EXP_02_EfficiencyAxiomCompleteness` checks sum of contributions plus base value against `decision_function` for baseline and perturbed samples.
* **Limitations:** Holds on raw decision function / margin output.

#### MR-EXP-03: Linear Attribution Shift Under Feature Perturbation
* **Rationale:** For a linear model $f(x) = \sum w_i x_i + b$ with independent background distribution, the SHAP value for feature $j$ is $\phi_j(x) = w_j (x_j - \mathbb{E}[X_j])$. When feature $j$ is shifted by $\Delta$ while holding all other features constant:
$$\phi_j(x') - \phi_j(x) = w_j \cdot \Delta.$$
Furthermore, the attributions of all other features $k \ne j$ remain exactly unchanged.
* **Input Transformation:** Add $\Delta > 0$ to feature $j$ in input $x$ to form $x'$.
* **Expected Property:** $|\phi_j(x') - \phi_j(x) - w_j \cdot \Delta| < 10^{-5}$ and $|\phi_k(x') - \phi_k(x)| < 10^{-5}$ for all $k \ne j$.
* **Test Implementation:** `explanation_relations.py::MR_EXP_03_LinearFeatureShiftAttribution` shifts feature 0 by $\Delta=2.5$ and checks observed attribution delta matches $w_0 \cdot 2.5$.
* **Limitations:** Applies to linear models explained with `LinearExplainer` on independent masker.

#### MR-EXP-04: Explanation Stability Monotonicity Under Noise Scaling
* **Rationale:** In `ExplanationStabilityAnalyzer`, explanation stability is defined as the mean cosine similarity between baseline SHAP attribution vector and perturbed vectors under Gaussian noise $\sigma$. As $\sigma$ increases, the perturbed points move further away from the local neighborhood, lowering or preserving cosine similarity in expectation:
$$\text{stability}(\sigma_{small}) \ge \text{stability}(\sigma_{large}).$$
* **Input Transformation:** Evaluate stability score under low noise $\sigma_1 = 0.01$ versus high noise $\sigma_2 = 0.60$.
* **Expected Property:** $\text{stability\_score}(\sigma_1) \ge \text{stability\_score}(\sigma_2) - 0.02$.
* **Test Implementation:** `explanation_relations.py::MR_EXP_04_StabilityNoiseMonotonicity` computes stability at $\sigma=0.01$ and $\sigma=0.60$ ($N=30$ repetitions) and asserts monotonic ordering.
* **Limitations:** Evaluated in statistical expectation with adequate repetitions.

#### MR-EXP-05: Explanation Invariance Under Metadata Header Injection
* **Rationale:** Explanations explain the model's decision on flow features. Injecting packet header metadata fields (such as `srcip`, `timestamp`, `sensor_id`) that are dropped during preprocessing must not alter the resulting SHAP feature contributions, base value, or top-$k$ feature rankings.
* **Input Transformation:** Inject metadata fields into raw sample $x$ to form $x'$ before explanation.
* **Expected Property:** $\text{top\_features}(x) == \text{top\_features}(x')$ in feature names, attribution values, and ranking.
* **Test Implementation:** `explanation_relations.py::MR_EXP_05_ExplanationMetadataInvariance` compares top-5 feature rankings and values before and after metadata injection.
* **Limitations:** Injected keys must be in `_DROP_PATTERNS` or non-feature schema.

---

## 4. Verification and Execution Results

### Summary Statistics
* **Total Relations Defined:** 27
* **Relations Passed:** 27
* **Relations Failed:** 0
* **Pass Rate:** **100.0%**
* **Total Execution Time:** ~2.15 seconds

### Full Relation Execution Matrix

| ID | Category | Relation Name | Status | Time (ms) |
|---|---|---|---|---|
| **MR-PRE-01** | `preprocessing` | Metadata Field Dropping Invariance | **PASS** | 205.06 |
| **MR-PRE-02** | `preprocessing` | Dictionary Key Insertion Order Invariance | **PASS** | 105.07 |
| **MR-PRE-03** | `preprocessing` | Out-of-Vocabulary Categorical Fallback Equivalence | **PASS** | 107.10 |
| **MR-PRE-04** | `preprocessing` | Batch Inference Isolation / Stateless Preprocessing | **PASS** | 87.49 |
| **MR-CAN-01** | `canonicalization` | Key Permutation Invariance (RFC 8785) | **PASS** | 1.26 |
| **MR-CAN-02** | `canonicalization` | Insignificant Whitespace Normalization | **PASS** | 0.11 |
| **MR-CAN-03** | `canonicalization` | ISO-8601 UTC Datetime Normalization | **PASS** | 0.06 |
| **MR-CAN-04** | `canonicalization` | Non-Finite Float Rejection Invariance | **PASS** | 0.06 |
| **MR-HASH-01** | `cryptographic_hashing` | Avalanche and Preimage Sensitivity | **PASS** | 0.06 |
| **MR-HASH-02** | `cryptographic_hashing` | Hash Chain Operand Non-Commutativity | **PASS** | 0.01 |
| **MR-HASH-03** | `cryptographic_hashing` | Merkle Tree Domain Separation | **PASS** | 0.01 |
| **MR-HASH-04** | `cryptographic_hashing` | Merkle Odd-Leaf Duplication Structural Invariance | **PASS** | 0.11 |
| **MR-VER-01** | `evidence_verification` | Inductive Chain Extension Invariance | **PASS** | 0.35 |
| **MR-VER-02** | `evidence_verification` | Monotonic Tamper Sensitivity | **PASS** | 0.20 |
| **MR-VER-03** | `evidence_verification` | Prefix Validity Under Truncation | **PASS** | 0.25 |
| **MR-VER-04** | `evidence_verification` | Non-Genesis Suffix Rejection | **PASS** | 0.11 |
| **MR-VER-05** | `evidence_verification` | Notary Artifact Payload-Digest Entanglement | **PASS** | 57.61 |
| **MR-PRED-01** | `prediction_behavior` | Metadata Field Invariance for Model Inference | **PASS** | 302.11 |
| **MR-PRED-02** | `prediction_behavior` | Input Feature Key Ordering Invariance | **PASS** | 262.99 |
| **MR-PRED-03** | `prediction_behavior` | Directional Monotonicity Under Attack Amplification | **PASS** | 84.83 |
| **MR-PRED-04** | `prediction_behavior` | Batch Row Isolation and Permutation Invariance | **PASS** | 326.12 |
| **MR-PRED-05** | `prediction_behavior` | Confidence Threshold Monotonic Uncertainty | **PASS** | 108.69 |
| **MR-EXP-01** | `explanation_behavior` | Shapley Null Player Axiom (Zero-Weight Feature) | **PASS** | 61.35 |
| **MR-EXP-02** | `explanation_behavior` | Shapley Efficiency Axiom (Completeness) | **PASS** | 67.36 |
| **MR-EXP-03** | `explanation_behavior` | Linear Attribution Shift Under Perturbation | **PASS** | 74.95 |
| **MR-EXP-04** | `explanation_behavior` | Explanation Stability Monotonicity Under Noise | **PASS** | 133.39 |
| **MR-EXP-05** | `explanation_behavior` | Explanation Invariance Under Metadata Header Injection | **PASS** | 158.39 |

---

## 5. Execution Guide & CI Gate

### Command-Line Execution
Run all relations:
```bash
python scripts/metamorphic_harness.py
```

Run relations for a single category:
```bash
python scripts/metamorphic_harness.py --category prediction_behavior
```

Generate machine-readable JSON:
```bash
python scripts/metamorphic_harness.py --json > results/metamorphic-report.json
```

Via Makefile:
```bash
make metamorphic
```

### Pytest Integration
The entire suite is integrated directly into the standard test runner:
```bash
pytest backend/tests/unit/test_metamorphic.py -v
```

### CI Gate Configuration
To enforce metamorphic relations in automated pull-request validation:
```yaml
- name: Metamorphic Testing Gate
  run: |
    python scripts/metamorphic_harness.py --json | tee results/metamorphic-report.json
    # Exit code is non-zero if any relation fails
```
