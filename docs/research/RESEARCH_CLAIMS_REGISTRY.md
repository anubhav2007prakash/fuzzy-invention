# SentinelCrypt AI — Research Claims Registry

**Created:** 2026-09-21 (registration of claims existing in the repository as of that date)
**Scope:** All substantive research, security, and scientific claims in `README.md`, `docs/`, `docs/research/`, `docs/presentation/`, `docs/security/`, `docs/xai/`, `docs/ml/`, `docs/cryptography/`, `docs/ai/`, `SentinelCrypt_AI_All_Documents/`, UI copy, API handlers, and checked-in result artifacts.
**Rule applied:** A claim is marked `SUPPORTED` only when the repository itself contains a measured, reproducible result or a defensive architecture that preserves the claim. A claim is marked `UNTESTED` when it is stated as a direction or a plan. A claim is marked `NOT_SUPPORTED` when the codebase contradicts it or reports a result that falsifies it. Unsupported numerical/quantitative claims have been removed or rewritten.

---

## How to read this document

- `Status`: UNTESTED | SUPPORTED | PARTIALLY_SUPPORTED | NOT_SUPPORTED | INCONCLUSIVE
- `Evidence required`: the minimal artifact needed to call the claim supported.
- `Experiment supporting it`: EXP-A..H, EXP-ROBUSTNESS, BENCHMARK, or a test file.
- `Dataset`: what was actually run.
- `Metric`: the quantity claimed.
- `Assumptions`: conditions that must hold.
- `Limitations`: boundaries of the evidence.
- `Counter-evidence`: results that contradict or bound the claim.
- `Current status`: as of registry creation.

---

## A. Machine-Learning Intrusion Detection Claims

### A-1. "The system trains Logistic Regression and Random Forest baselines for intrusion detection."
- Claim: LR and RF classifiers exist, train, evaluate, and serve predictions through the API.
- Evidence required: `backend/tests` passing; API `POST /models/train`, `GET /models`.
- Experiment supporting it: Phase-1/2 implementation; `backend/tests/unit/test_ml_models.py`, `test_training_api.py`, `test_training_service.py`, `test_evaluator.py`.
- Dataset: Synthetic deterministic flow generator (`generate_flow_dataset`, 10 features, binary label).
- Metric: Test accuracy ~0.80 at fixed seed; macro-F1/P/R/AP; leakage checks.
- Assumptions: Training on the synthetic corpus, fixed seeds, and the model API as implemented.
- Limitations: These are baseline models on a synthetic proxy; they are not a real-world IDS result.
- Counter-evidence: None in repo. The models are plain-sklearn classifiers on 10-dimensional synthetic features.
- Current status: **SUPPORTED** (implementations exist and are tested; performance numbers are task-specific, not claimed as universal).

### A-2. "SentinelCrypt is an IDS research platform, not a production security product."
- Claim: Research prototype; educational/portfolio use; not a production SIEM/IDS.
- Evidence required: Documentation and UI disclaimers.
- Experiment supporting it: `docs/00_PROJECT_CHARTER.md`, `docs/01_PRODUCT_CONCEPT.md`, `docs/02_PRD.md`, `docs/10_UI_UX_SPECIFICATION.md`, `README.md`, `SECURITY.md`, `docs/security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md`.
- Dataset: N/A.
- Metric: N/A (scope statement).
- Assumptions: The repository scope as documented.
- Limitations: None. This is the project's own explicit scope.
- Counter-evidence: None.
- Current status: **SUPPORTED** (stated in multiple documents and UI).

### A-3. "No new cryptographic algorithm is invented; SHA-256 and Ed25519 are the primitives."
- Claim: The ledger uses standard SHA-256; the notary uses Ed25519; no new crypto primitive is claimed.
- Evidence required: `backend/app/cryptography/*`; `docs/cryptography/*`.
- Experiment supporting it: Phase-4 implementation; `test_hashing.py`, `test_verifier.py`, `test_notary.py`, `test_reference_differential.py`.
- Dataset: N/A.
- Metric: Correct hash length (64 hex), deterministic canonical serialization, signature verification success.
- Assumptions: Standard-library/maintained `hashlib`, `cryptography` package behavior, correct key handling.
- Limitations: Cryptographic assumptions are on the algorithm/library, not on deployment correctness.
- Counter-evidence: `docs/security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md` (T-13, T-14, T-15, T-16) and `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md` flag key custody and host compromise.
- Current status: **SUPPORTED** (explicit non-invention, documented trust boundaries).

### A-4. "SHAP is used for local and global explanation; SHAP is not causal proof."
- Claim: SHAP attributions are model-dependent and are explicitly not causal.
- Evidence required: `backend/app/xai/*`; UI copy; `docs/xai/*`.
- Experiment supporting it: EXP-B; `test_shap_validation.py`; `docs/xai/XAI_METHODOLOGY.md`, `docs/xai/EXPLANATION_RELIABILITY.md`.
- Dataset: Synthetic deterministic flow data.
- Metric: Local accuracy, stability under Gaussian perturbation, top-k overlap, Spearman.
- Assumptions: The SHAP library computes the attributions; perturbation design is within bounds.
- Limitations: Attribution stability does not equal causal correctness; single-sample stability is a weak evidential base.
- Counter-evidence: None; docs explicitly say "Stability does not prove causal correctness or truth."
- Current status: **SUPPORTED** (disclaimed as non-causal and validated only as stability).

### A-5. "SHAP explanation stability is a measurable quantity."
- Claim: Attribution stability can be measured as mean cosine similarity over repetitions at noise levels.
- Evidence required: `backend/app/xai/stability.py`; `test_xai_stability.py` (or equivalent); result artifact.
- Experiment supporting it: EXP-B; `backend/test/unit/test_xai_stability.py`.
- Dataset: Synthetic deterministic data; one attack sample, 8 repetitions per sigma.
- Metric: `stability_score ∈ [0,1]`; per-level curve; global `overall_mean_stability`.
- Assumptions: A fitted TreeExplainer/linear explainer; deterministic background; bounded noise.
- Limitations: Single-sample, single-model, 8 repetitions per level. Not a universal stability claim.
- Counter-evidence: None in repo; `CH-20260923-194438.json` (EXP-B) records the measured stability curve.
- Current status: **SUPPORTED** for a single controlled synthetic run; generalizes only as a methodology.

### A-6. "Explanation stability does not prove explanation faithfulness or causal correctness."
- Claim: Stability is a consistency measure, not a truth guarantee.
- Evidence required: `docs/xai/EXPLANATION_RELIABILITY.md`; `docs/xai/XAI_METHODOLOGY.md`; UI copy.
- Experiment supporting it: EXP-B interpretation text.
- Dataset: N/A.
- Metric: N/A (rationale statement).
- Assumptions: None.
- Limitations: N/A.
- Counter-evidence: None.
- Current status: **SUPPORTED** (explicit caveats in docs).

---

## B. Data and Datasets Claims

### B-1. "UNSW-NB15 and CICIDS2017 are the intended real datasets for cross-dataset evaluation."
- Claim: UNSW-NB15 (9 attack classes) and CICIDS2017 (Wednesday working hours) are registered/approved datasets for the pipeline.
- Evidence required: `backend/app/api/v1/datasets.py` validation and dataset registry entries; dataset documentation.
- Experiment supporting it: `docs/00_PROJECT_CHARTER.md` and `docs/09_DATABASE_SCHEMA.md` schema descriptions; `docs/research/EXPERIMENT_DESIGN.md` planned-UNSW/CICIDS section.
- Dataset: UNSW-NB15 (49 features + label/attack_cat) and CICIDS2017 (78 features + label).
- Metric: Schema compatibility, checksum validation, provenance capture.
- Assumptions: Approved, public, authorized datasets; the pipelines named in the docs are configured.
- Limitations: In the current implementation, these two datasets are declared as planned; the benchmark sources `unsw_nb15` and `cicids2017` are synthetic proxies labelled as such. No real UNSW-NB15/CICIDS2017 capture is part of the current measured results.
- Counter-evidence: `backend/app/research/benchmark.py` `BENCHMARK_SOURCES` labels `UNSW-NB15` and `CICIDS2017` as `synthetic_proxy`; `EXP-A`/`EXP-D` run on synthetic partitions; the README says real cross-dataset generalization is planned future work.
- Current status: **PARTIALLY_SUPPORTED** — dataset descriptions exist, but no verified real UNSW-NB15/CICIDS2017 ingestion is in the current registry/results.

### B-2. "Current experiments validly represent cross-dataset generalization from UNSW-NB15 to CICIDS2017."
- Claim: EXP-A measures generalization from one dataset to another.
- Evidence required: `backend/app/services/experiment_service.py::run_exp_a`, `experiments/EXP-A-cross-dataset/run.py`, `results/exp_a_cross_dataset.json`.
- Experiment supporting it: EXP-A (synthetic source/target partitions with shift_scale 1.0 vs 1.65).
- Dataset: Synthetic partitions (10 features) with distribution shift.
- Metric: `delta_f1 = in_distribution.F1 - out_of_distribution.F1`.
- Assumptions: The synthetic shift is an acceptable proxy for dataset shift.
- Limitations: The result file and UI report a **0.0% F1 drop** on the synthetic proxy. This is a synthetic-data outcome, not a real cross-dataset measurement; extrapolation to UNSW-NB15/CICIDS2017 is explicitly not claimed.
- Counter-evidence: `results/evidence/EXP-A/experiment.json` and `metrics.json` both record `delta_f1: 0.0`; `docs/research/EXPERIMENT_DESIGN.md` explicitly marks real UNSW/CICIDS as planned future work; `docs/ai/RESEARCH_CONTEXT.md` describes the hypothesis in terms of real datasets. The UI copy on `Experiments.jsx` still reads "How significantly does detection accuracy degrade when a model trained on UNSW-NB15 is evaluated on CICIDS2017 distribution?" — that question is not answered by the implemented synthetic run.
- Current status: **PARTIALLY_SUPPORTED (falsified as stated)** for real UNSW-CICIDS; **SUPPORTED** for synthetic distribution-shift measurement.

### B-3. "The data generator produces correct UNSW/NIDCS-shaped features and class separation."
- Claim: Synthetic data approximates the two benchmark datasets.
- Evidence required: `backend/app/ml/data/synthetic.py`; `test_*` comparing distributions; real dataset ingestion.
- Experiment supporting it: `backend/app/ml/data/synthetic.py`; `backend/tests/unit/test_preprocessing.py` (synthetic detection, missing value detection).
- Dataset: Synthetic partitions (shift_scale/attack_ratio/missing_rate).
- Metric: Feature distribution, class balance, missingness.
- Assumptions: The generator's embedded disclaimers hold.
- Limitations: Only synthetic control data; no real traffic bytes are ingested in the current measured results.
- Counter-evidence: `SYNTHETIC_DISCLAIMER`; `BENCHMARK_SOURCES["unsw_nb15"]["note"]` and `["cicids2017"]["note"]` say "Not real UNSW-CICIDS capture data."
- Current status: **SUPPORTED** as a clearly-labeled synthetic generator.

### B-4. "Dataset provenance is recorded: name, source, file hash, row/feature counts, target column, validation status."
- Claim: Dataset registration capture includes provenance and checksums.
- Evidence required: `backend/app/db/models/dataset.py` (or model), `backend/app/services/dataset_service.py`; `test_*`.
- Experiment supporting it: Phase-1/2 implementation; `backend/tests/unit/test_dataset_service.py`, `test_file_security.py`, `test_db_integrity.py`.
- Dataset: Uploaded CSV files.
- Metric: Stored `file_hash` (SHA-256), `row_count`, `feature_count`, `target_column`, `validation_status`.
- Assumptions: Upload validation as implemented.
- Limitations: SQLite/SQLite default; no external trusted source verification.
- Counter-evidence: None in repo.
- Current status: **SUPPORTED** (as implemented).

### B-5. "Synthetic data with control is a valid substitute for real captures in reproduction."
- Claim: Deterministic synthetic flows make results reproducible without external datasets.
- Evidence required: `backend/app/research/benchmark.py` provenance notes; result artifacts; reproducibility tests.
- Experiment supporting it: BENCHMARK; `test_benchmark.py`; `test_reproducibility.py`.
- Dataset: Synthetic proxies.
- Metric: `bit_identical_across_runs: true`; `f1_spread` ~0.
- Assumptions: Same code versions, same seeds, same generators.
- Limitations: Reproducibility of a synthetic benchmark does not establish real-capture fidelity.
- Counter-evidence: None; the docs require explicit origin labels.
- Current status: **SUPPORTED** for synthetic-protocol reproducibility, with explicit origin labels.

---

## C. Cryptographic Ledger Claims

### C-1. "Canonical JSON (`sort_keys`, `separators=(',',':')`, float normalization, UTC ISO-8601) makes the payload digest reproducible."
- Claim: Canonicalization yields a deterministic byte string per payload.
- Evidence required: `backend/app/cryptography/canonicalization.py`; `test_reference_differential.py`; `test_property_based.py`.
- Experiment supporting it: Phase-4; `test_hashing.py`; `test_reference_differential.py`; property suite.
- Dataset: N/A.
- Metric: Equality against a reference oracle; digest length 64 hex; NaN/Infinity rejected with ValueError.
- Assumptions: The reference implementation matches the production canonicalizer.
- Limitations: Unicode and deep-nesting coverage depends on the property suite; currently the differential tests are ASCII-centric (see `docs/research/PROPERTY_TESTING.md` P6/P7).
- Counter-evidence: `docs/research/PROPERTY_TESTING.md` notes `ensure_ascii=False` survivors need Unicode property tests; `docs/security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md` T-05 lists NaN/Infinity as malformed-input concerns.
- Current status: **SUPPORTED** for the tested canonicalization rules.

### C-2. "Record hash = SHA-256(previous_hash || payload_hash); genesis = 64 zeros."
- Claim: The chain formula is as documented.
- Evidence required: `backend/app/cryptography/hash_chain.py`; `test_hashing.py`; `test_verifier.py`.
- Experiment supporting it: Phase-4; `test_hashing.py`; `test_verifier.py`.
- Dataset: N/A.
- Metric: Deterministic digest; genesis verification.
- Assumptions: Hex-encoded concatenation as implemented.
- Limitations: This is an append-only local chain, not a distributed ledger.
- Counter-evidence: `docs/security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md` T-09..T-16; `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md` section 2.
- Current status: **SUPPORTED** for the implemented formula.

### C-3. "The ledger detects payload mutation, previous_hash rewrite, and intermediate record deletion."
- Claim: EXP-C detects these three controlled tampering scenarios.
- Evidence required: `backend/app/services/experiment_service.py::run_exp_c`; `results/evidence/EXP-C/*`; `backend/tests/unit/test_ledger_security.py`; `backend/tests/integration/test_audit_api.py`.
- Experiment supporting it: EXP-C (12-block in-memory chain; 3 attacks).
- Dataset: Synthetic in-memory records.
- Metric: `tamper_detection_rate: "100.0%"`; each attack `detected: true`; `clean_chain_valid: true`.
- Assumptions: The verifier receives the full chain; no external tip/record-count anchor exists.
- Limitations: Results are on a local, controlled, 12-block synthetic chain; the implementation cannot detect a tail deletion unless an external expected tip/length exists (T-10); it does not prevent, encrypt, or authenticate the database host.
- Counter-evidence: `backend/tests/unit/test_verifier.py`/metadata confirm prefix-without-tail verifies; `docs/security/THREAT_MODEL.md` "Ledger Threat Model" states the chain does not protect against a fully compromised host; `backend/tests/security/redteam.py` (and T-10) document deletion limitations.
- Current status: **SUPPORTED** for the tested scenarios, with explicit non-guarantees.

### C-4. "Verification is deterministic and reports each failure."
- Claim: The verifier recomputes hashes and returns failures.
- Evidence required: `backend/app/cryptography/verifier.py`; `test_verifier.py`; `test_ledger_security.py`.
- Experiment supporting it: Phase-4; tests.
- Dataset: N/A.
- Metric: `verified: false`, `failed_records` populated, first failure reported.
- Assumptions: Ordered records with the documented fields.
- Limitations: Does not detect a deleted tail absent external anchoring (T-10).
- Counter-evidence: None; the code and tests document this behavior.
- Current status: **SUPPORTED**.

### C-5. "The chain is not a blockchain and does not provide consensus, immutability, or resistance to a compromised administrator."
- Claim: The project explicitly disclaims blockchain semantics and strong trust claims.
- Evidence required: `docs/05_HLD_SYSTEM_ARCHITECTURE.md`; `docs/MASTER_SPECIFICATION.md`; `docs/security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md`; `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md`.
- Experiment supporting it: Documentation-only.
- Dataset: N/A.
- Metric: N/A (scope and threat-model statements).
- Assumptions: None.
- Limitations: N/A.
- Counter-evidence: None; the docs are consistent and conservative.
- Current status: **SUPPORTED** (these are explicit, repeated disclaimers).

### C-6. "The notary public key is a local demo key; verification needs no server; a self-presented key is not a production trust anchor."
- Claim: Ed25519 signing/verification is implemented; trust anchor relies on operator distribution.
- Evidence required: `backend/app/cryptography/notary.py`; `backend/tests/unit/test_notary.py`; `backend/tests/fixtures/security/`.
- Experiment supporting it: Phase-5/7; notary tests.
- Dataset: N/A.
- Metric: `verify` true/false; fingerprint comparison.
- Assumptions: The verifier's local trust anchor is trusted.
- Limitations: No KMS/HSM; no rotation/revocation; local unencrypted demo key; key self-signature is not signer authentication (T-13).
- Counter-evidence: `docs/security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md` T-13; `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md` section 5 and 8.
- Current status: **SUPPORTED** as implemented, with explicit trust-boundary caveats.

### C-7. "A valid signature over a supplied public key proves only that the matching private key signed the digest; it does not identify the operator."
- Claim: Artifact identity depends on out-of-band fingerprint verification.
- Evidence required: `backend/app/cryptography/notary.py`; `backend/tests/unit/test_notary.py`; `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md` section 5.
- Experiment supporting it: Notary tests.
- Dataset: N/A.
- Metric: Signature consistency vs. fingerprint mismatch.
- Assumptions: The consumer keeps a trusted anchor.
- Limitations: Self-signed/bundled keys can be forged by an attacker with key control; no external ledger witness.
- Counter-evidence: `backend/tests/unit/test_notary.py`; `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md` section 2/8.
- Current status: **SUPPORTED**.

### C-8. "The notary `signed_at` is a process-generated UTC string, not a trusted timestamp token; it is not bound into the signature."
- Claim: Timestamps are not authenticated proof.
- Evidence required: `backend/app/cryptography/notary.py`; `backend/tests/unit/test_notary.py`; `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md` sections 5/7.
- Experiment supporting it: Notary tests.
- Dataset: N/A.
- Metric: Signature success unchanged after envelope-time alteration.
- Assumptions: Local clock state.
- Limitations: Replay and clock skew remain possible; no authenticated timestamping.
- Counter-evidence: None; the tests document the limitation.
- Current status: **SUPPORTED**.

### C-9. "Audit verification detects modifications to records it receives; it cannot prove the host has not deleted or replaced the entire ledger/database."
- Claim: The verifier is an internal consistency check, not an external witness.
- Evidence required: `backend/app/cryptography/verifier.py`; `docs/security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md` T-09/T-10/T-15/T-16; `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md` section 3.
- Experiment supporting it: Documentation; red-team tests.
- Dataset: N/A.
- Metric: N/A (threat-scope statement).
- Assumptions: None.
- Limitations: T-10/T-15/T-16 remain; `db_integrity.py` only catches relational inconsistencies, not host-level deletion.
- Counter-evidence: None; the threat model explicitly enumerates these limits.
- Current status: **SUPPORTED** as an explicit limitation.

---

## D. Cryptographic Overhead and Performance Claims

### D-1. "SHA-256 + canonicalization adds single-digit-microsecond cost per inference (<10% of the pipeline)."
- Claim: Crypto overhead is small and bounded under 10%.
- Evidence required: `backend/app/services/experiment_service.py::run_exp_d` crypto measurement; `results/exp_d_model_comparison.json`; benchmark consistency.
- Experiment supporting it: EXP-D (`canonicalization_and_sha256_us`).
- Dataset: Synthetic flow data; 500 iterations of canonicalize+SHA-256.
- Metric: `cryptographic_overhead.canonicalization_and_sha256_us`; `relative_overhead_pct`.
- Assumptions: The 500-iteration microbenchmark reflects typical inference; timing is wall-clock.
- Limitations: Microbenchmark, not a production benchmark; numbers vary by CPU/load; `relative_overhead_pct` is derived from one measured payload.
- Counter-evidence: `results/challenges/CH-20260923-194820.json` and `CH-20260923-195247.json` record different `relative_overhead_pct` values (`~12.0%`, `~14.0%`), showing the percentage is not a stable measured constant.
- Current status: **PARTIALLY_SUPPORTED** — the measured microseconds are real, but the "<10%" bound is not stable across runs and is a heuristic claim.

### D-2. "Pipeline stages have documented latencies (dataset ingestion, preprocessing, prediction, SHAP, evidence, ledger write, verification)."
- Claim: End-to-end stage costs can be measured.
- Evidence required: `backend/app/research/benchmark.py::run_pipeline_benchmark`; `results/scalability.json`; `backend/tests/unit/test_benchmark.py`.
- Experiment supporting it: BENCHMARK pipeline item.
- Dataset: Synthetic flows.
- Metric: `stages_ms` per stage; `end_to_end_ms`; `xai_overhead_pct`; `crypto_overhead_pct`.
- Assumptions: Synthetic data and a single model configuration.
- Limitations: Wall-clock microbenchmark; scaling exponents are log-log slopes over one seed.
- Counter-evidence: None in repo.
- Current status: **SUPPORTED** as a measured, clearly-scoped benchmark.

### D-3. "Hash-chain verification scales linearly with record count; Merkle supports O(log n) membership proofs."
- Claim: Chain verification cost is linear; Merkle proof cost is logarithmic.
- Evidence required: `backend/app/research/integrity_comparison.py`; `results/exp_g_integrity_comparison.json`; `backend/tests/unit/test_new_experiments.py`.
- Experiment supporting it: EXP-G.
- Dataset: Synthetic payloads.
- Metric: `chain.verify_ms` vs `merkle.verify_ms` and `membership_proof_ms` across sizes; scaling exponents.
- Assumptions: Same canonical payload set; the chain has no sublinear membership proof by design.
- Limitations: Scaling exponents are statistical estimates; chain membership is a full-walk equal to full verify (documented note).
- Counter-evidence: None in repo.
- Current status: **SUPPORTED** for the measured comparison.

---

## E. Experiment-Specific Claims

### E-1. "EXP-A measures cross-dataset generalization and reports a generalization gap."
- Claim: EXP-A trains on a source and evaluates on a shifted target, reporting `delta_f1`.
- Evidence required: `run_exp_a`, `results/exp_a_cross_dataset.json`, `experiments/EXP-A-cross-dataset/run.py`.
- Experiment supporting it: EXP-A (synthetic, source shift_scale 1.0 vs target 1.65).
- Dataset: Synthetic partitions.
- Metric: `delta_f1`, `delta_accuracy`; observed drop reported as 0.0.
- Assumptions: The synthetic shift is representative of cross-dataset shift.
- Limitations: Real UNSW-CICIDS is planned future work; the observed synthetic gap is 0.0, so there is no measured degradation to report.
- Counter-evidence: `docs/research/EXPERIMENT_DESIGN.md` and `docs/ai/RESEARCH_CONTEXT.md` frame the real-dataset version as the research question; the implemented run does not answer it.
- Current status: **PARTIALLY_SUPPORTED** — the experiment exists and runs, but the real-dataset generalization hypothesis is **UNTESTED** and the synthetic result is not a measured degradation.

### E-2. "EXP-B measures SHAP stability under Gaussian noise with a target cosine stability > 0.85."
- Claim: Explanations stay stable above a threshold under low sensor noise.
- Evidence required: `run_exp_b`, `results/exp_b_xai_stability.json`, `backend/tests/unit/test_experiments.py`.
- Experiment supporting it: EXP-B.
- Dataset: Synthetic flows; one attack sample; noise levels {0.01..0.20}, 8 repetitions.
- Metric: `overall_mean_stability` and per-level curve.
- Assumptions: The threshold was chosen before measurement.
- Limitations: Single sample; 8 repetitions; no statistical error bars; the threshold is a target, not an acceptance criterion reported in the result.
- Counter-evidence: Result artifact records the measured curve; no evidence of a universal >0.85 claim.
- Current status: **SUPPORTED** as a methodology; the 0.85 target is an informational goal, not a demonstrated universal.

### E-3. "EXP-C reports tamper detection rate and per-scenario detection; the verifier is the authoritative detector."
- Claim: EXP-C simulates payload mutation, pointer rewrite, and deletion, and reports 100% detection.
- Evidence required: `run_exp_c`, `results/evidence/EXP-C/experiment.json`+`.json`, `backend/tests/unit/test_ledger_security.py`.
- Experiment supporting it: EXP-C.
- Dataset: Synthetic in-memory chain (12 blocks).
- Metric: `clean_chain_valid: true`; `tamper_detection_rate: "100.0%"`; each `detected: true`.
- Assumptions: The verifier receives full, ordered records; no external expected tip anchor.
- Limitations: 3 scenarios; 12-block chain; no tail-deletion guarantee absent an external anchor; no production guarantee.
- Counter-evidence: `backend/tests/unit/test_verifier.py` and metadata confirm prefix-without-tail verifies; `docs/security/THREAT_MODEL.md` and T-10 bound the claim.
- Current status: **SUPPORTED** for the tested scenarios; universal 100% is **UNTESTED** and bounded.

### E-4. "EXP-D compares LR and RF on accuracy, F1, ROC-AUC, training/inference time, and cryptographic overhead."
- Claim: EXP-D measures both models under the same protocol and reports runtime/crypto overhead.
- Evidence required: `run_exp_d`, `results/exp_d_model_comparison.json`, `experiments/EXP-D-model-comparison/run.py`.
- Experiment supporting it: EXP-D (1500 synthetic samples, 75/25 split).
- Dataset: Synthetic flows.
- Metric: Accuracy/F1/ROC-AUC; `inference_time_us`; `cryptographic_overhead_us`; `relative_overhead_pct`.
- Assumptions: Both models share the same protocol and synthetic data.
- Limitations: Microbenchmark of crypto cost; CPU-dependent; the "<10%" heuristic is not stable (see D-1).
- Counter-evidence: None; the result exists but is task-specific.
- Current status: **SUPPORTED** as measured.

### E-5. "EXP-F measures predictive quality and operational costs for A–E SentinelCrypt component arms."
- Claim: EXP-F compares ML only, ML+XAI, ML+cryptographic evidence, ML+XAI+evidence, and the benchmark's full provenance-envelope arm.
- Evidence required: `backend/app/research/ablation.py`; `results/exp_f_ablation_v2.json`; `backend/tests/unit/test_new_experiments.py`; `docs/research/ABLATION_STUDY.md`.
- Experiment supporting it: EXP-F, framework version 2.
- Dataset: Generated synthetic flows.
- Metric: Precision, recall, F1, macro-F1, PR-AUC (plus accuracy, ROC-AUC, ECE, Brier), inference/explanation/evidence-generation/verification latency, traced Python memory, and scoped serialized evidence/manifest bytes; repeated arms are paired per run.
- Assumptions: Within each repeat, every arm shares one fitted model, one training-only-fitted preprocessor, one held-out set, and identical predictions.
- Limitations: This is a synthetic pipeline measurement, not a real-network effectiveness or full production deployment study. Model fitting is shared and excluded from per-arm latency. SHAP is sampled by default; memory excludes native allocations and model fitting; storage excludes DB/filesystem overhead. E's lineage manifest models the requested chain but is not the production persisted-artifact graph. Added components are not presumed to improve quality.
- Historical output: `results/exp_f_ablation.json` remains the previous framework's output and is not overwritten or relabeled by v2.
- Counter-evidence: The design predicts no quality gain from post-prediction XAI/evidence; any observed paired quality delta is treated as a defect to investigate.
- Current status: **SUPPORTED** as a measured synthetic component/cost comparison; no generalization or efficacy claim.

### E-6. "EXP-G compares hash-chain vs Merkle on verify time, membership proof, storage, and tamper detection."
- Claim: EXP-G measures the two integrity architectures under identical payloads.
- Evidence required: `backend/app/research/integrity_comparison.py`; `results/exp_g_integrity_comparison.json`; `backend/tests/unit/test_new_experiments.py`.
- Experiment supporting it: EXP-G.
- Dataset: Synthetic payloads.
- Metric: build/verify/ms, membership proof, storage bytes, `mutation_all_sizes`, `omission_all_sizes`.
- Assumptions: The Merkle leaves are domain-separated; chain has no sublinear proof.
- Limitations: Size ladder is 100/500/2000; timing is wall-clock; verdict is per-size.
- Counter-evidence: None; the result exists.
- Current status: **SUPPORTED** for the measured comparison.

### E-7. "EXP-H measures cross-method explanation agreement (SHAP vs permutation vs built-in importance) with top-k overlap and Spearman."
- Claim: Agreement among three importance methods is quantified; stability under noise is reported.
- Evidence required: `backend/app/research/xai_agreement_study.py`; `backend/tests/unit/test_xai_agreement.py`; `results/exp_h_xai_agreement.json`.
- Experiment supporting it: EXP-H.
- Dataset: Synthetic flows; noise levels {0, 0.05, 0.10}.
- Metric: `mean_topk_overlap`, `mean_spearman`, `agreement_by_noise`, `agreement_stable_under_noise`.
- Assumptions: The three methods are run on the same evaluation split; top-k is fixed.
- Limitations: Agreement is a property of the methods on this data; it is not agreement with ground truth.
- Counter-evidence: None; the result exists.
- Current status: **SUPPORTED** as measured agreement.

---

## F. Security and Trust Claims

### F-1. "The platform is a research prototype, and its controls protect evidence under explicit trust assumptions."
- Claim: Evidence integrity, input validation, and safe file handling are documented and tested.
- Evidence required: `docs/security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md`; `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md`; `backend/tests/unit/test_file_security.py`, `test_config.py`, `test_hashing.py`, `test_security_redteam.py`, `test_notary.py`, `test_db_integrity.py`.
- Experiment supporting it: Documentation and tests.
- Dataset: N/A.
- Metric: Test coverage of file paths, config, hashing, tamper detection, notary, relational invariants.
- Assumptions: Local deployment; trusted OS/runtime; controlled operator.
- Limitations: No production authentication/authorization; no key rotation; no external witness; host compromise is out of scope.
- Counter-evidence: `docs/security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md` (22 threat rows), `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md` section 7.
- Current status: **SUPPORTED** as a bounded research-prototype security posture.

### F-2. "Unauthenticated API and default mode allow reads/mutations; this is not authorization."
- Claim: Demo/Research mode is an operational guard, not access control.
- Evidence required: `backend/app/research/modes.py`; `backend/app/api/v1/*.py` mode guard; `docs/security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md` T-14; `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md` section 8.
- Experiment supporting it: Mode state and endpoint authorization tests.
- Dataset: N/A.
- Metric: `endpoint_allowed` denies POST outside demo scope; mode state.
- Assumptions: Default mode and route mapping as implemented.
- Limitations: No RBAC, MFA, CSRF, or tenant isolation; production remote exposure is unsafe without Priority 0 controls.
- Counter-evidence: None; the docs explicitly recommend authentication and RBAC before untrusted use.
- Current status: **SUPPORTED** as documented and implemented.

### F-3. "The ledger detects tampering in records it receives; it does not prevent host-level deletion or full chain rewrite."
- Claim: Ledger verification is internal evidence, not an external witness.
- Evidence required: `docs/security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md` T-09..T-16; `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md` sections 3/5/7.
- Experiment supporting it: Documentation; `test_db_integrity.py`, `test_verifier.py`.
- Dataset: N/A.
- Metric: N/A (threat-scope statement).
- Assumptions: None.
- Limitations: T-10/T-15/T-16 remain; no remote witness, no external expected tip anchor.
- Counter-evidence: None; the docs are explicit.
- Current status: **SUPPORTED**.

### F-4. "Pickle/joblib artifacts are executable inputs and are not a cryptographic trust boundary; they must be verified before load."
- Claim: Deserialization safety is bounded by artifact integrity.
- Evidence required: `docs/security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md` T-07/T-16; `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md` section 2/4.
- Experiment supporting it: Documentation; red-team tests.
- Dataset: N/A.
- Metric: N/A (threat-scope statement).
- Assumptions: Local filesystem trust and key custody.
- Limitations: No production key management, no isolated worker default.
- Counter-evidence: None; the docs are explicit.
- Current status: **SUPPORTED**.

### F-5. "CLI/script-only verification and research tools do not constitute a secure deployment without infra changes."
- Claim: Verifier tools are stand-alone stdlib; deployment needs hardening.
- Evidence required: `scripts/sentinel_verify.py`; `docs/security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md` T-16; `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md` section 8.
- Experiment supporting it: Documentation; CLI tests.
- Dataset: N/A.
- Metric: CLI exit behavior; verification report fields.
- Assumptions: The CLI is used in a controlled environment.
- Limitations: CI workflows are checkout-only skeletons; dependency pinning and release provenance are not established.
- Counter-evidence: None; the docs are explicit.
- Current status: **SUPPORTED**.

---

## G. Reproducibility and Evidence-Integrity Claims

### G-1. "Same seed and configuration produce bit-identical quality metrics; latency/memory are non-identity wall-clock measurements."
- Claim: Deterministic reproduction is tracked with a `f1_spread` near zero.
- Evidence required: `backend/app/research/benchmark.py`; `test_benchmark.py`; `results/reports/*.json`.
- Experiment supporting it: BENCHMARK.
- Dataset: Synthetic proxies.
- Metric: `bit_identical_across_runs`; `f1_spread < 1e-9`; `identity_scope` text.
- Assumptions: Same package versions and seeds.
- Limitations: Reproducibility of a synthetic benchmark does not imply real-world reproducibility.
- Counter-evidence: None; the code and tests document this carefully.
- Current status: **SUPPORTED**.

### G-2. "Result and configuration hashes are canonical SHA-256 digests over stripped envelope content."
- Claim: Deterministic hashes cover the scientific payload, not wall-clock fields.
- Evidence required: `backend/app/services/experiment_service.py::calculate_result_hash`, `calculate_configuration_hash`, `build_run_manifest`; `test_reference_differential.py`.
- Experiment supporting it: ExperimentService enrichment tests.
- Dataset: N/A.
- Metric: 64-character hex; same payload/key order yields same digest.
- Assumptions: Canonicalization of the stripped envelope matches the reference.
- Limitations: `generated_at` and `git` are excluded from identity; tamper-evident only as long as the envelope fields are stable.
- Counter-evidence: None; implementation is consistent.
- Current status: **SUPPORTED**.

### G-3. "Evidence packages contain experiment.json, metrics.json, reproducibility-manifest.json, verification-report.json, README.md, plus file hashes and a package hash."
- Claim: Export produces a structured, hash-bindable package.
- Evidence required: `backend/app/services/experiment_service.py::export_evidence_package`; `backend/tests/unit/test_experiments.py::test_export_evidence_package_writes_expected_files`.
- Experiment supporting it: Evidence export tests.
- Dataset: N/A.
- Metric: `package_hash` over `files`; five documented files; status `exported`.
- Assumptions: Files are written and hashed correctly; no checksum for plots.
- Limitations: No signed package format or external key binding in v1.
- Counter-evidence: None in repo.
- Current status: **SUPPORTED** for a deterministic package export (no external signature).

### G-4. "The reproducibility package hash is a pure function of the exported result."
- Claim: `package_hash` depends only on the file tree and hashes.
- Evidence required: `backend/app/research/reproducibility.py`; `backend/tests/unit/test_reproducibility.py`.
- Experiment supporting it: Reproducibility tests.
- Dataset: N/A.
- Metric: Same tree → same hash; environment/dates excluded from the content hash.
- Assumptions: `hash_file` and `canonicalize` are deterministic.
- Limitations: Same result content in a different artifact layout cannot be compared.
- Counter-evidence: None; the implementation is documented and tested.
- Current status: **SUPPORTED**.

### G-5. "Database integrity audit catches relational inconsistencies (sequence gaps, duplicate sequences, orphans, impossible timestamps)."
- Claim: Temporal/referential checks are implemented and tested.
- Evidence required: `backend/app/research/db_integrity.py`; `backend/tests/unit/test_db_integrity.py`.
- Experiment supporting it: DB integrity tests.
- Dataset: SQLite rows.
- Metric: `consistency` statuses; detected anomaly classes.
- Assumptions: The audit runs over the full chain or over relevant tables.
- Limitations: Does not cover host-level deletion or external witness (T-10); migration-fallback can mask drift.
- Counter-evidence: `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md` section 3.
- Current status: **SUPPORTED** for relational invariants, with bounded scope.

---

## H. UI- and Result-Artifact Claims

### H-1. "UI shows the current metrics and status from stored experiment results, not fabricated numbers."
- Claim: UI values come from stored/returned results.
- Evidence required: `frontend/src/pages/Experiments.jsx`; `frontend/src/pages/Models.jsx`; `frontend/src/pages/Dashboard.jsx`; `frontend/test/pages.test.jsx`.
- Experiment supporting it: UI integration and vitest tests.
- Dataset: Stored experiment JSON artifacts.
- Metric: Rendered values are a function of stored results.
- Assumptions: API returns authoritative data.
- Limitations: Some UI copy still describes real UNSW-CICIDS scenarios (H-2); formatting helpers handle nulls and attack classes explicitly.
- Counter-evidence: `docs/research/EXPERIMENT_DESIGN.md` and `EXP-A` result both say synthetic; `EXPERIMENT_META` descriptions in `Experiments.jsx` reference real datasets in the question prompt text, which is a copy issue, not a measured-result issue.
- Current status: **SUPPORTED** as an implementation rule; copy in some UI strings should be read as planned/hypothesis text.

### H-2. "EXP-A question text references real UNSW-NB15/CICIDS2017 while the implementation uses synthetic partitions."
- Claim: UI copy describes the real-dataset hypothesis.
- Evidence required: `frontend/src/pages/Experiments.jsx` (`EXPERIMENTS_META`).
- Experiment supporting it: Copy + synthetic data.
- Dataset: Synthetic partitions.
- Metric: N/A (copy vs data mismatch).
- Assumptions: None.
- Limitations: The question is a hypothetical framing; the measured run does not answer it. This should be rewritten to state synthetic-scope or planned future work.
- Counter-evidence: `results/evidence/EXP-A/experiment.json` (`note: "Not real UNSW-NB15/CICIDS2017 datasets."`), `docs/research/EXPERIMENT_DESIGN.md`.
- Current status: **PARTIALLY_SUPPORTED** — UI copy needs rewriting to match the synthetic implementation.

### H-3. "Dashboard model table and Predictions show trustworthy values."
- Claim: Model cards show F1 macro/P/R/PR-AUC/ROC-AUC from stored metrics; Prediction history shows class/confidence/proof.
- Evidence required: `frontend/src/pages/Models.jsx`; `frontend/src/pages/Predictions.jsx`; API response contracts.
- Experiment supporting it: UI vitest tests and live click-through.
- Dataset: Stored model/prediction rows.
- Metric: Formatted percent strings and status badges from the API.
- Assumptions: The API returns the documented fields; dead fields in UI were fixed by the UI batch.
- Limitations: Performance/targeting claims are UI-only; they do not add new measurements.
- Counter-evidence: The UI batch fixed dead fields (model table, prediction PROB, audit payload fields); tests pass.
- Current status: **SUPPORTED** after the UI batch fix.

### H-4. "The dashboard hero and tab copy describe multi-stage cryptographic guardrails."
- Claim: UI copy describes the architecture accurately.
- Evidence required: `frontend/src/pages/Dashboard.jsx`; `frontend/src/components/layout/Header.jsx`; `Frontend` test coverage.
- Experiment supporting it: UI tests and live probes.
- Dataset: Stored audit records.
- Metric: Copy correctness.
- Assumptions: None.
- Limitations: Copy is branding, not a measured claim.
- Counter-evidence: None; the copy is consistent with the architecture.
- Current status: **SUPPORTED** as UI copy.

---

## I. Claims with No Measured Result (Claims to Close)

| # | Claim | Status | Evidence needed |
|---|---|---|---|
| I-1 | Real UNSW-NB15/CICIDS2017 ingestion yields defensible detection/generalization results | **UNTESTED** | Real dataset registration, training, and EXP-A on actual captures |
| I-2 | Explanation stability > 0.85 is a reliable quality gate | **UNTESTED** | Pre-registered threshold, multiple samples, confidence intervals, population stability |
| I-3 | Hash chain detects every deletion (not just middle/first) | **NOT_SUPPORTED** as a universal | External expected tip/record-count anchor; design of the verifier |
| I-4 | Crypto overhead is < 10% of pipeline consistently | **NOT_SUPPORTED** as a stable claim | Repeated runs at fixed hardware with a pre-registration | 

---

## J. Triage Summary (top-level)

- **SUPPORTED (no caveat):** scope/disclaimer claims; model baselines; SHAP non-causality; explanation stability methodology; canonicalization/hash-chain formula; tamper detection on the 3 controlled scenarios; verification determinism; non-blockchain; notary trust anchor caveats; timestamp non-authentication; internal-verifier limitation; deterministic reproduction; result/config hashes; evidence package export; package-hash purity; DB integrity audit; UI-driven-from-storage rule.
- **PARTIALLY_SUPPORTED:** B-1/B-2 (real UNSW-CICIDS planned; synthetic proxy fills now); D-1 (`<10%` not stable); C-3/C-4 (100% only for tested scenarios; tail deletion bounded); E-1 (synthetic gap 0.0; real version untested); E-2 (0.85 target, not a demonstrated gate); E-4/E-5/E-6/E-7 (measured per-task); F-1/F-2/F-3/F-4/F-5 (bounded security posture with Priority 0 requirements); G-1..G-5 (reproducibility and export are supported with documented boundaries); H-3/H-4 (UI-driven-from-storage, after UI batch).
- **NOT_SUPPORTED / UNTESTED as stated:** I-1, I-2, I-3, I-4; H-2 copy should be rewritten.
- **Unsupported numerical or scientific claims have been removed or rewritten** in the parent documents; this registry records which claims remain valid and which must be labeled as planned, bounded, or unmeasured.

---

## K. Key Libraries and Files Referenced

- `backend/app/services/experiment_service.py` — experiment runners, envelopes, hashes, trust profile, evidence export.
- `backend/app/research/benchmark.py` — synthetic-proxy benchmark protocol with origin labels.
- `backend/app/research/integrity_comparison.py`, `ablation.py`, `xai_agreement_study.py`, `robustness.py` — EXP-G/F/H/ROBUSTNESS.
- `backend/app/cryptography/{canonicalization,hashing,hash_chain,verifier,reference}.py` — crypto core.
- `docs/research/EXPERIMENT_DESIGN.md`, `docs/research/RESEARCH_PROPOSAL.md`, `docs/research/RESEARCH_GAP.md`, `docs/research/PROPERTY_TESTING.md`.
- `docs/security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md`, `docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md`, `docs/security/THREAT_MODEL.md`.
- `backend/tests/unit/test_experiments.py`, `test_ledger_security.py`, `test_verifier.py`, `test_hashing.py`, `test_notary.py`, `test_reference_differential.py`, `test_benchmark.py`, `test_new_experiments.py`, `test_robustness_experiment.py`, `test_db_integrity.py`, `test_security_redteam.py`.
- `frontend/src/pages/Experiments.jsx`, `Models.jsx`, `Dashboard.jsx`, `Predictions.jsx`, `AuditLedger.jsx`, `Explainability.jsx`, `ProfessorMode.jsx`, `Provenance.jsx`, `Benchmark.jsx`.
- `results/evidence/EXP-A`, `EXP-B`, `EXP-C`, `EXP-D`, `EXP-F`, `EXP-G`, `EXP-H`, `EXP-ROBUSTNESS`, `results/challenges`, `results/reports`, `results/tables`.
