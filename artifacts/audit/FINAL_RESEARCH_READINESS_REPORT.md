# SentinelCrypt Research Readiness Audit

**Audit date:** 2026-10-02  
**Audited revision:** `a5d5120` plus the working-tree contents present during this audit  
**Scope:** Engineering, security, machine learning, XAI, cryptography, research, and documentation  
**Method:** Repository-grounded review and attempted local validation; no external literature review or live deployment assessment was performed.

## Executive conclusion

The repository contains a substantial research-prototype implementation and unusually broad documentation for its evidence, security assumptions, experiments, and limitations. The inspected materials support bounded claims about implemented workflows and controlled synthetic experiments. They do **not** establish production security, real-world intrusion-detection efficacy, external validity, trusted time, distributed immutability, or publication-level novelty.

This audit cannot confirm the current test, frontend build, security-scanner, or experiment status: the configured Python environment lacks the project dependencies and pytest, and Node.js execution is blocked by the active sandbox. A repository-wide Python compilation attempt also found a syntax error in a differential test. Accordingly, no runtime test pass counts or experiment results are asserted here. **The evidence is insufficient to declare SentinelCrypt secure or research-ready.**

## Audit scope and evidence limits

The review considered the repository's application and experiment code, test inventory, checked-in security and research documents, dependency manifests, and local validation results. Relevant source-of-record documents include the [Research Claims Registry](../../docs/research/RESEARCH_CLAIMS_REGISTRY.md), [Independent Reproduction Protocol](../../docs/research/INDEPENDENT_REPRODUCTION_PROTOCOL.md), [Statistical Methodology](../../docs/research/STATISTICAL_METHODOLOGY.md), [Trust and Security Assumptions](../../docs/security/TRUST_AND_SECURITY_ASSUMPTIONS.md), [Platform Threat Model](../../docs/security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md), and [Supply-Chain Security](../../docs/security/SUPPLY_CHAIN_SECURITY.md).

The worktree was not clean: at audit time it contained 52 tracked changes and 400 untracked paths (452 status entries total). The report therefore describes the available working-tree snapshot, not just commit `a5d5120`; this audit does not attribute those pre-existing changes to this task. The existing audit document at this path contained stale, unverified test outcomes and broad claims. It was replaced with this report rather than carried forward as current evidence.

“Verified” below means supported by code or documentation inspected in this checkout. It does not mean that runtime behavior was independently exercised unless a validation result explicitly says so.

## Verified strengths

### Engineering

- The repository has distinct backend, frontend, ML, research, cryptography, and test areas. The application and script Python sources passed `compileall` in this environment; this establishes parse/bytecode compilation only, not importability or correct runtime behavior.
- The API uses FastAPI request and response schemas in multiple routes. Tests for API validation and integration are present, but were not executable here.
- A database-integrity audit endpoint and related tests are present. The security documentation characterizes verification as read-only; runtime non-mutation has not been re-exercised in this audit.
- The frontend has separate test and production-build scripts in its package manifest. Neither could be executed because Node.js failed during startup under the sandbox restriction.

### Security

- Repository documentation explicitly treats API clients, uploaded data, serialized model artifacts, local storage, host administrators, dependencies, and timestamps as trust concerns. It does not describe the local hash chain as blockchain or distributed immutability.
- There is a security regression test corpus, as well as file-security and API-validation test modules. The test inventory is evidence that checks are authored, not that they currently pass.
- The supply-chain manifest-consistency command completed successfully: `scripts/supply_chain.py verify` reported that dependency manifests and the frontend lockfile are aligned. This does not report dependency vulnerability status.
- The project documents selected upload/path protections and the risk of loading untrusted pickle/joblib artifacts. Actual deployment isolation and access control remain operator responsibilities.

### Machine learning and XAI

- The checked-in synthetic flow generator labels its output synthetic, accepts deterministic seeds, and exposes controlled changes such as attack ratio, missingness, and feature scaling. Its feature distributions are authored in code and cannot stand in for observations from a deployment population.
- The ML documentation and experiment protocols distinguish preprocessing fit data from held-out data and describe class-sensitive metrics rather than relying solely on accuracy.
- Calibration and robustness laboratories document their bounded experimental scope and state that raw probabilities and synthetic perturbation results do not establish operational confidence or robustness.
- XAI documentation says feature attributions are model- and explainer-dependent and are not causal proof.

### Cryptography and evidence

- The repository contains canonicalization, SHA-256 hashing, hash-chain verification, an Ed25519 research notary, Merkle-related code, a reference implementation, and a standalone evidence-verification CLI. Their cross-implementation equivalence and standards conformance are not established by the presence of these components.
- Protocol and trust documents correctly bound local hash-chain guarantees: internal consistency is not truth, completeness, trusted chronology, distributed immutability, or signer identity without an externally trusted public-key binding.
- Offline verification and protocol-version handling are documented. The package's independent verification behavior was not executed in this audit because required Python dependencies are absent.

### Research and documentation

- The repository records explicit research claims and limitations, experiment designs, ablation definitions, calibration, robustness, statistical methodology, reproducibility, falsification, provenance, and security assumptions.
- Statistical documentation describes design-dependent summaries, trial-level raw-data references, and no automatic p-value or significance claims.
- The reproduction protocol warns that registered external datasets are not necessarily consumed by every experiment and that current synthetic results are not real UNSW-NB15/CICIDS2017 measurements.

## Verified weaknesses

### Engineering and validation

- **The complete backend test suite did not run.** The configured Python environment has no `pytest`; checks also found FastAPI, SQLAlchemy, NumPy, pandas, scikit-learn, SHAP, Hypothesis, and HTTPX unavailable.
- **A test source file does not compile.** `python -m compileall -q backend scripts` failed at `backend/tests/differential/test_hashing_differential.py:168` with `IndentationError: unexpected indent`. This is a static compilation failure, not a pytest assertion failure.
- **The frontend test, build, and audit commands did not run.** Node.js 24 failed at process startup with `EPERM: operation not permitted, lstat 'C:\\'`. The error was reported as a sandbox restriction; no alternate-path workaround was attempted.
- **The experiment CLI could not initialize.** `scripts/run_experiment.py --help` failed importing NumPy. No experiment result was generated or validated in this audit.
- `git diff --check` reported a new blank line at EOF in the current working-tree diff for `backend/app/core/exceptions.py:136`. That file was already modified in the dirty worktree; this audit did not change it.
- The repository diagnostics tool reported no errors, but that does not negate the independent `compileall` failure above.

### Security

- No local `gitleaks`, `pip-audit`, `bandit`, `ruff`, or `flake8` executable was available. No secret-scan or Python dependency vulnerability result was obtained during this audit.
- The Python dependency declarations use version ranges and the repository documents the absence of a Python resolver lockfile. The npm lockfile's consistency was checked, but frontend vulnerability scanning could not run.
- The checked-in Ed25519 notary is a research/demo mechanism whose private key is stored locally without encryption. A public key included in the artifact can establish signature consistency under that key, but not the identity of the operator unless its fingerprint is trusted independently.
- Plugin code and model deserialization execute in the application process; the repository's documentation does not establish an OS-level plugin sandbox or safe deserialization of untrusted artifacts.
- The repository documents that general authentication/authorization, privileged-host protection, and external key/time anchoring are outside its local evidence guarantees. Their adequacy depends on deployment configuration not inspected here.

### ML, XAI, and research validity

- The synthetic data generator assigns class-conditional feature distributions and a configurable label ratio. Metrics on these data measure behavior on the generated task, not detection efficacy, false-alert burden, or prevalence in a real network.
- Synthetic random/stratified partitions do not establish independence across hosts, sessions, capture sites, campaigns, or time. The reviewed evidence does not establish real-data, group-held-out or temporal validation.
- Baseline models and bounded perturbations do not establish generalization to unseen datasets, attack families, or production distribution shift. No external data experiment was executed in this audit.
- Calibration is documented as binary and finite-sample. Its documented split design is a useful control, but calibration under real traffic, prevalence changes, and temporal/site shift remains unverified.
- `ExplanationStabilityAnalyzer` returns cosine similarity `1.0` when either attribution vector is zero and converts an individual perturbed-explanation exception into a similarity of `0.0`. Consumers must distinguish these cases from ordinary successful stability observations; a mean alone can obscure failed repetitions.
- The A–E ablation shares the fitted model, holdout, predictions, and probabilities across component arms. It can compare scoped component costs, but cannot support a claim that adding XAI or cryptographic evidence improves predictive quality.
- Experiment UI copy frames an experiment as an UNSW-NB15-to-CICIDS2017 comparison ([Experiments.jsx](../../frontend/src/pages/Experiments.jsx)), while the documented current experiment design uses synthetic data ([EXPERIMENT_DESIGN.md](../../docs/research/EXPERIMENT_DESIGN.md)). The UI wording is not evidence that the real-dataset experiment was run.
- The statistical methodology documents few-trial and sampling limitations. Confidence intervals over configured repeats cannot fix a non-representative sampling frame or establish population-level performance.
- Python environment resolution is not locked. Recording `pip freeze` for a particular reproduction helps preserve that environment but does not make future installs resolve identically.

### Cryptography, provenance, and external validity

- A local hash chain can be recomputed after a sufficiently privileged rewrite. A valid prefix may remain verifiable after tail removal unless an expected tip or completeness checkpoint is authenticated elsewhere.
- A self-contained signature artifact does not authenticate its embedded public key, establish trusted signing time, or prove that the signed experiment data were truthful.
- The application's implemented notary is Ed25519. Release-signing documentation describing other mechanisms is workflow guidance; it is not evidence that RSA-PSS or OpenPGP signing is implemented in the application.
- Production canonicalization uses sorted-key Python JSON serialization ([canonicalization.py](../../backend/app/cryptography/canonicalization.py)), while the reference implementation explicitly describes its behavior as a local convention rather than RFC 8785/JCS ([reference/canonical.py](../../backend/app/cryptography/reference/canonical.py)). The experiment design uses RFC 8785 wording ([EXPERIMENT_DESIGN.md](../../docs/research/EXPERIMENT_DESIGN.md)). Standards interoperability therefore remains unverified.
- Production chain verification detects sequence gaps ([verifier.py](../../backend/app/cryptography/verifier.py)), while the reference verifier's documented contract does not treat gaps as hard failures ([reference/verify.py](../../backend/app/cryptography/reference/verify.py)). The empty-ledger case also returns `verified=True`; this means there were no records to check, not that a populated chain was verified. These differences qualify claims of independent verifier equivalence.
- Evidence verification establishes only the properties checked by the selected verifier and supplied package. It cannot recreate unavailable data, dependencies, model runtime, or experiment context, and no full scientific reproducibility claim follows from the package alone.
- The literature-review material is a framework/search plan rather than a completed, systematic comparison. A combination of existing technologies is not, by itself, evidence of novelty.

## Unresolved risks

1. **Current behavioral correctness:** no backend or frontend tests ran in this environment, and one differential test file fails Python compilation.
2. **Public or multi-user deployment:** authentication, authorization, resource isolation, deployment hardening, and access controls require deployment-specific evidence.
3. **Data validity and external validity:** real, authorized datasets with independent capture/time/group splits and documented label harmonization are needed for IDS efficacy claims.
4. **Supply-chain exposure:** local dependency consistency passed, but vulnerability and secret scans did not run; Python versions are not locked.
5. **Key and chronology trust:** key custody/rotation, independently pinned signer identity, external timestamping, and external ledger checkpoints are not established by local files alone.
6. **Negative and failed research outcomes:** a report/dashboard must preserve incomplete, failed, inconclusive, and negative runs rather than selectively presenting successful outcomes. The current status could not be runtime-validated.
7. **Reproducibility:** clean-room reproduction, external-dataset access, and evidence verification were not tested in this audit; dependency and hardware differences remain.

## Unsupported claims

The repository evidence reviewed here does not support claims that:

- SentinelCrypt is “secure,” production-ready, or safe for untrusted public/multi-tenant deployment.
- Synthetic benchmark performance establishes real-world IDS efficacy, operational false-positive rates, or cross-dataset generalization.
- OOD or robustness measurements prove that traffic is malicious or that a model is robust to arbitrary/adaptive attacks.
- SHAP or another attribution establishes causation, attacker intent, or explanation truth.
- A probability score is automatically calibrated confidence in real-world outcomes.
- SHA-256, a hash chain, or a self-contained evidence package gives blockchain properties, distributed immutability, truth, or completeness.
- A self-contained signature alone proves signer identity, non-repudiation under a trusted identity, or trusted creation time.
- An offline evidence package guarantees complete scientific reproducibility.
- Statistical significance, population-level confidence, or novelty has been established without the corresponding study and evidence.
- RFC 8785/JCS interoperability has been established merely by sorted-key JSON serialization.

## Validation record

| Area | Command/check | Result | Interpretation |
|---|---|---|---|
| Backend tests | `python -m pytest backend/tests -q` | **Blocked** — `No module named pytest` | No test cases ran; no pass/fail count can be reported. |
| Python parse/compile | `python -m compileall -q backend/app scripts` | **Passed** | Application and script files compiled; runtime imports and behavior were not exercised. |
| Full backend tree compile | `python -m compileall -q backend scripts` | **Failed** — `IndentationError` at `backend/tests/differential/test_hashing_differential.py:168` | Differential test source has a syntax/indentation error in this checkout. |
| Frontend tests | `npm.cmd --prefix frontend test -- --run` | **Blocked by sandbox** — Node startup failed with `EPERM` on `C:\\` | Frontend tests did not run. |
| Frontend production build | `npm.cmd --prefix frontend run build` | **Blocked by sandbox** — same Node startup error | No bundle was produced. |
| Frontend dependency audit | `npm.cmd audit --prefix frontend --audit-level=high` | **Blocked by sandbox** — same Node startup error | No advisory result was obtained. |
| Dependency manifest check | `python scripts/supply_chain.py verify` | **Passed** — manifests and frontend lockfile aligned | Structural consistency only; not a vulnerability or license approval. |
| Experiment CLI | `python scripts/run_experiment.py --help` | **Failed to initialize** — `ModuleNotFoundError: numpy` | No experiment ran; no scientific result was validated. |
| Security tool availability | PATH check for `gitleaks`, `pip-audit`, `bandit`, `ruff`, `flake8` | **Unavailable** | No corresponding local scans were executed. |
| Worktree hygiene | `git diff --check` | **Failed** — extra blank line at `backend/app/core/exceptions.py:136` | Existing dirty-tree whitespace issue; not changed in this audit. |
| Workspace diagnostics | Problems panel | No errors reported | Does not override the Python compilation failure. |

The Node.js `EPERM` error is attributed to the active sandbox policy for `C:\\`. Completing frontend test/build/audit validation requires that policy to permit the Node process access it needs. The Python test/experiment blockers require the repository's declared dependencies and test tools to be available in an approved environment. No dependencies were installed and no alternate-path workaround was attempted.

## Reproducibility issues

- The audited working tree contains 452 tracked/untracked status entries; reproducing this exact snapshot requires preserving that state, not checking out only `a5d5120`.
- The Python environment is incomplete and the dependency graph is not resolver-locked.
- Experiments could not be launched because NumPy is absent. Therefore this report does not certify current experiment outputs, raw-data references, evidence exports, or offline verification.
- Frontend behavior and generated assets were not built or tested.
- Real datasets require authorized access and independent checksum provenance; the current synthetic generator is not a substitute.
- Timing, memory, and storage measurements remain specific to their documented measurement boundaries and execution environment.

## Recommended next actions

### Immediate validation blockers

1. Correct the indentation error in `backend/tests/differential/test_hashing_differential.py:168`, then run `python -m compileall -q backend scripts` and the complete backend test suite in a supported, dependency-complete environment. Preserve the exact commands, environment versions, and test counts.
2. Update the sandbox policy to permit Node.js operation on the blocked path, then run the complete frontend test suite, production build, and dependency audit. Do not treat the sandbox failure as a frontend pass or fail.
3. Run the configured CI security workflow in an environment with the required scanners and record Gitleaks, Python advisory, npm advisory, SBOM, and license-inventory outputs. A clean scanner result is not proof that dependencies are secure.
4. Rerun the project's required experiment validations and export/verify evidence packages only after the tests pass. Retain raw results, configuration, commit, dependency environment, and verifier output.
5. Resolve the whitespace finding in `backend/app/core/exceptions.py` as part of its owning change, then require a clean `git diff --check`.

### Research and operational evidence

6. Evaluate authorized real traffic with site-, host/session-, campaign-, and time-aware splits; disclose label mapping, sampling, class prevalence, exclusions, and per-class errors.
7. Preregister the estimand, baselines, trial unit, and decision costs. Use independent data collection units for generalization claims; report failures and negative results alongside successful runs.
8. Test calibration and robustness on temporally/site-held-out data and under justified prevalence, missingness, sensor, and feature shifts. Keep OOD detection distinct from attack classification.
9. Make XAI reports preserve explainer failures and degenerate attributions explicitly; validate faithfulness/stability on multiple samples and methods before making explanation claims.
10. For stronger evidence claims, pin signer identity out-of-band, define key rotation/revocation, and use independent timestamp/checkpoint services when signer identity, freshness, or completeness matters.
11. Complete the literature review with reproducible search methods and compare the claimed contribution against simpler baselines before asserting novelty.
12. Test production canonicalization against RFC 8785/JCS interoperability vectors, and make the reference verifier enforce the same chain invariants as production or explicitly narrow its independent-verification claim. Distinguish an empty ledger from a verified populated ledger in caller-facing results.
13. Align the experiment interface copy with the implemented synthetic experiment design unless and until the real UNSW-NB15/CICIDS2017 path is implemented and evidenced.
14. Repeat the full workflow from a clean checkout and clean environment, document every deviation, and update the audit only with freshly captured validation evidence.

## Final disposition

This audit found real implementation and documentation strengths, but also material validation, security, and scientific-evidence gaps. Several core validation suites could not run, and one backend test source fails compilation. The available evidence supports describing SentinelCrypt as a research prototype with selected controlled capabilities; it does not justify declaring the platform secure or research-ready.
