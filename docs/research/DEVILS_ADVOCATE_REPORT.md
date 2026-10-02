# SentinelCrypt Devil's Advocate Research Report

**Review posture:** Hostile but scientifically fair  
**Scope:** Claims about the SentinelCrypt application, its ML and XAI results, cryptographic evidence, experiments, security posture, reproducibility, and research contribution.  
**Evidence basis:** Repository documentation, implementation, and checked-in test/artifact references. This report does not independently rerun experiments, inspect external datasets, or validate claims against external literature. No unobserved results are inferred.

## How to read this report

Each finding states the criticism, repository evidence, severity, current mitigation, remaining uncertainty, and a concrete experiment or review that could resolve the uncertainty.

Severity is a prioritization judgment, not a measured probability:

- **Critical:** blocks a consequential claim central to the project as currently evidenced.
- **High:** materially limits validity, security, or generalizability.
- **Medium:** leaves a meaningful but narrower uncertainty.
- **Low:** primarily affects interpretation, scope, or future confidence.

This review does not presume that SentinelCrypt is ineffective. It asks what the available evidence actually establishes and what observations could disprove it.

## Findings

### DA-01 — Synthetic data cannot establish real-world IDS efficacy

1. **Criticism:** The central performance evidence is generated from a known synthetic process. High scores on this task may reflect how the generator encodes the labels rather than detection of real malicious network traffic.
2. **Evidence:** [EXPERIMENT_DESIGN.md](./EXPERIMENT_DESIGN.md) says current implemented experiments use synthetic data; [synthetic.py](../../backend/app/ml/data/synthetic.py) constructs benign and attack feature values from separate class-conditional distributions and explicitly says the output is not real telemetry. The [reproduction protocol](./INDEPENDENT_REPRODUCTION_PROTOCOL.md) also cautions that registered datasets are not necessarily consumed by each experiment.
3. **Severity:** Critical for operational-efficacy claims; low for the narrower claim that a controlled synthetic pipeline runs.
4. **Current mitigation:** Synthetic scope and non-generalization disclaimers are explicit; the repository distinguishes synthetic proxies from real UNSW-NB15/CICIDS2017 data.
5. **Remaining uncertainty:** No real capture dataset results in the cited evidence establish detection performance, false-alarm burden, or robustness in deployment.
6. **Experiment that could resolve it:** Preregister a protocol on authorized, versioned, checksum-verified real datasets; train on one capture/source and test on a temporally and organizationally separate capture; report per-class confusion matrices, prevalence, PR-AUC, and uncertainty. Preserve raw splits and dataset hashes.

### DA-02 — Synthetic sampling does not represent a deployment sampling frame

1. **Criticism:** Deterministic pseudo-random rows generated from a hand-coded distribution are not a sample of network environments, devices, attack campaigns, or time periods. Repeated seeds do not add new populations.
2. **Evidence:** [synthetic.py](../../backend/app/ml/data/synthetic.py) creates a fixed 10-feature synthetic schema with a configurable attack ratio and seed. The experiments document repeated splits over generated data, not independently sampled networks; for example, [ROBUSTNESS_LAB.md](./ROBUSTNESS_LAB.md) says repeated partitions reuse one generated dataset.
3. **Severity:** High for population-level interpretation.
4. **Current mitigation:** Reports label synthetic inputs and avoid claiming that repeated partitions represent independent real-world samples.
5. **Remaining uncertainty:** The degree to which the chosen generator resembles any intended deployment remains unvalidated.
6. **Experiment that could resolve it:** Define a target population and sampling frame; collect or obtain independent captures across sites, times, device types, and attack families; compare feature and label distributions to the synthetic generator before treating it as a proxy.

### DA-03 — Feature coverage is narrow and may encode shortcuts

1. **Criticism:** The current synthetic flow model uses ten aggregate numeric features and a binary label. It may omit context required to distinguish operationally meaningful traffic and may create easy label proxies (for example, TTL or packet-count ranges) that real data do not share.
2. **Evidence:** The feature schema in [EXPERIMENT_DESIGN.md](./EXPERIMENT_DESIGN.md) lists `dur`, packet/byte counts, rates, TTLs, and loads. [synthetic.py](../../backend/app/ml/data/synthetic.py) samples sharply distinct ranges for benign and attack classes, including TTL and packet quantities. The same design document says real-dataset feature mapping is future work.
3. **Severity:** High for claims about broad IDS coverage.
4. **Current mitigation:** Feature names and synthetic-generating rules are inspectable, and the project does not currently claim real-dataset cross-schema compatibility.
5. **Remaining uncertainty:** No feature-ablation or shortcut analysis establishes which synthetic variables drive performance or whether real benign/attack overlap is represented.
6. **Experiment that could resolve it:** On authorized real data, perform grouped feature ablations, permutation/conditional importance checks, and cross-source testing; specifically test whether performance collapses when suspicious proxy features such as TTL are removed or shifted.

### DA-04 — Class prevalence and minority-class performance remain deployment-unknown

1. **Criticism:** An experiment with a chosen synthetic `attack_ratio` cannot establish performance under the prevalence and class composition of a target network. Macro metrics help but do not by themselves establish acceptable alert burden or minority-family recall.
2. **Evidence:** The synthetic generator defaults to `attack_ratio=0.3` ([synthetic.py](../../backend/app/ml/data/synthetic.py)). [metrics.py](../../backend/app/ml/evaluation/metrics.py) reports macro/weighted metrics, class distribution, and binary false-positive/false-negative rates, but its own notes say the pipeline does not currently apply class weighting or resampling. The real deployment prevalence is not represented by that configurable synthetic parameter.
3. **Severity:** High for operational deployment claims.
4. **Current mitigation:** Class distribution and per-class reports are included; PR-AUC and error-rate metrics are available, avoiding reliance on accuracy alone.
5. **Remaining uncertainty:** Real attack prevalence, attack-family support, and acceptable false-positive cost are unknown. Metrics at a synthetic prevalence may not transfer.
6. **Experiment that could resolve it:** Evaluate on temporally held-out real traffic with the natural prevalence preserved; report per-family precision/recall, PR curves at operational thresholds, false positives per unit time, confidence intervals, and sensitivity to prevalence changes.

### DA-05 — Sample-level splitting may not prevent dependence leakage in real captures

1. **Criticism:** Fitting preprocessing on training rows is necessary but does not prevent leakage from near-duplicate flows, shared sessions, hosts, capture windows, or labels derived from the same attack campaign crossing a random split.
2. **Evidence:** [test_leakage_prevention.py](../../backend/tests/unit/test_leakage_prevention.py) and the [ablation protocol](./ABLATION_STUDY.md) address training-only preprocessing and stratified row splits. The currently documented real datasets and cross-dataset procedure are not yet implemented; the existing synthetic generator has no real session/site grouping to test.
3. **Severity:** High for any later real-data metric claim; medium for the bounded synthetic experiments.
4. **Current mitigation:** Preprocessors are fitted on training partitions, and the repository has leakage-focused tests.
5. **Remaining uncertainty:** The repository evidence does not establish group-, host-, campaign-, or time-isolated evaluation for real network captures.
6. **Experiment that could resolve it:** Create a leakage audit that identifies capture/session/host/campaign grouping fields; compare random-row splits with group-held-out and forward-in-time splits, deduplicate flows, and quantify performance changes. Keep the split manifest with the raw results.

### DA-06 — Two baseline model families are not a competitive or comprehensive model study

1. **Criticism:** Logistic Regression and Random Forest are useful baselines, but performance for these selected configurations cannot establish superiority, robustness, or a general conclusion about ML-based IDS.
2. **Evidence:** The [Research Claims Registry](./RESEARCH_CLAIMS_REGISTRY.md) describes these two baselines; the [ablation study](./ABLATION_STUDY.md) lists these as its supported model types and says model fitting is shared among component arms. The current framework does not establish that model/hyperparameter selection was conducted on a representative real-data benchmark.
3. **Severity:** Medium for implementation claims; high if extrapolated to a general model-performance claim.
4. **Current mitigation:** Claims are framed as baseline implementations, and the ablation design does not state that extra XAI/evidence components improve prediction quality.
5. **Remaining uncertainty:** Whether conclusions persist across stronger baselines, tuned configurations, different seeds, and operationally relevant decision costs is unknown.
6. **Experiment that could resolve it:** Predefine a modest comparator set and tuning budget, use nested or otherwise separated model-selection/evaluation data, include simple rules and relevant established baselines, and report both predictive quality and training/inference cost on the same external test data.

### DA-07 — “Cross-dataset generalization” is presently synthetic distribution transfer

1. **Criticism:** A shifted partition generated by one function is not equivalent to transfer between independently collected datasets, organizations, or collection pipelines.
2. **Evidence:** [EXP-A design](./EXPERIMENT_DESIGN.md) defines source/target partitions using `shift_scale` and attack-ratio changes in synthetic data. The [claims registry](./RESEARCH_CLAIMS_REGISTRY.md) labels real UNSW-NB15/CICIDS2017 generalization untested/planned and records that the synthetic experiment did not demonstrate the intended real-dataset question.
3. **Severity:** High if called cross-dataset generalization without the qualifier “synthetic”; low if described as a controlled shift experiment.
4. **Current mitigation:** Documentation explicitly says real-dataset cross-validation is future work and cautions against interpreting synthetic proxies as those datasets.
5. **Remaining uncertainty:** No evidence establishes performance transfer across actual dataset schemas, collection methods, or attack taxonomies.
6. **Experiment that could resolve it:** Run train-on-source/test-on-target with two independently collected, authorized datasets; publish feature mapping, exclusions, label harmonization, train/test boundaries, and per-class results. Include reverse-direction transfer where scientifically meaningful.

### DA-08 — The shift and robustness perturbations cover only selected synthetic changes

1. **Criticism:** A finite set of feature scaling/noise perturbations does not cover temporal drift, new attack families, concept drift, sensor failure, missingness patterns, adaptive evasion, or correlated changes in real traffic.
2. **Evidence:** [ROBUSTNESS_LAB.md](./ROBUSTNESS_LAB.md) explicitly limits its synthetic bounded coordinate-wise noise and says it is not a formal certificate. [EXPERIMENT_DESIGN.md](./EXPERIMENT_DESIGN.md) describes a particular synthetic scaling/TTL shift rather than a measured operational shift.
3. **Severity:** High for any broad “robust” or “handles distribution shift” claim.
4. **Current mitigation:** The experiment is named and documented as a sensitivity laboratory, not a robustness guarantee; limitations identify the perturbation scope.
5. **Remaining uncertainty:** There is no evidence on the prevalence or severity of the tested perturbations in target environments.
6. **Experiment that could resolve it:** Derive perturbation families from authorized capture comparisons and documented sensor faults; evaluate temporal and site-held-out data with bounded corruption, missingness, covariate and label shift, and report per-condition failures, not only averages.

### DA-09 — SHAP attribution is not an explanation of causal or attacker intent

1. **Criticism:** SHAP attributes model output relative to an explainer/background configuration. Correlated features, unrealistic feature combinations, choice of baseline, and model misspecification can produce plausible-looking but misleading explanations.
2. **Evidence:** [XAI_METHODOLOGY.md](../xai/XAI_METHODOLOGY.md) and [SHAP implementation](../../backend/app/xai/shap_explainer.py) state the explanation is model-dependent and not causal. The implementation uses a background sample for the linear explainer and TreeExplainer for the random forest. [EXPERIMENT_DESIGN.md](./EXPERIMENT_DESIGN.md) describes one attack sample for its original stability protocol.
3. **Severity:** High if explanations are presented as causal reasons or ground truth; medium for model-attribution visualization.
4. **Current mitigation:** The project documents non-causal interpretation and measures selected stability properties.
5. **Remaining uncertainty:** The validity of the chosen explainer/background, behavior under correlated features, and agreement with domain experts are not established by stability alone.
6. **Experiment that could resolve it:** Compare SHAP with independent explanation methods and domain-reviewed cases; test local accuracy, feature correlation sensitivity, realistic conditional perturbations, counterfactual validity, and fidelity against the model. Blind domain experts to model output and measure agreement.

### DA-10 — Explanation stability can overstate reliability in edge cases

1. **Criticism:** Stability under the selected perturbations measures consistency, not faithfulness; additionally, implementation conventions can make edge cases look artificially stable or failures look like valid low scores.
2. **Evidence:** [stability.py](../../backend/app/xai/stability.py) returns cosine similarity `1.0` if either attribution vector has zero norm and catches per-repeat explanation exceptions, recording similarity `0.0`. This exception handling may conceal a failed replicate inside an aggregate unless consumers inspect logs/results. The methodology itself lists explainer dependence and sample size as validity threats.
3. **Severity:** Medium.
4. **Current mitigation:** The project disclaims causal correctness and stores per-repetition similarities; the separate robustness experiment says its explanation failures fail the run rather than being converted to successful missing values.
5. **Remaining uncertainty:** Whether callers of `ExplanationStabilityAnalyzer` surface the failure information and how often zero-vector or exception cases occur in realistic use are not established here.
6. **Experiment that could resolve it:** Add fixtures for zero vectors and explainer exceptions, verify that the reporting contract distinguishes “identical zero signal” from measured stability and preserves failure counts; rerun stability across many samples, models, and realistic conditional perturbations.

### DA-11 — Calibration evidence is a synthetic, binary, finite-sample result

1. **Criticism:** A lower Brier score/ECE on one held-out synthetic sample does not show calibration on real traffic or after prevalence/distribution change. ECE is bin-dependent, and repeated method selection against the same test set can overfit that set.
2. **Evidence:** [PREDICTION_CALIBRATION_LAB.md](./PREDICTION_CALIBRATION_LAB.md) defines the measurements and explicitly warns about held-out sample size, binning, and post-selection. It limits current calibration to binary 0/1 targets and identifies sigmoid/isotonic minimum support gates.
3. **Severity:** High for real-world probability or decision claims; medium for the synthetic method demonstration.
4. **Current mitigation:** Calibration uses separate fit/calibration/test partitions; preprocessing is fitted only on model-fit data; methods have explicit eligibility thresholds and no silent fallback.
5. **Remaining uncertainty:** Calibration across sites, time, subgroups, rare classes, and shifted prevalence is untested; finite-sample reliability-bin uncertainty remains.
6. **Experiment that could resolve it:** Evaluate pre-registered calibration on a new, temporally held-out, authorized dataset with natural prevalence. Report reliability bins with counts/uncertainty, Brier score, ECE sensitivity to binning, subgroup metrics, and performance after controlled prevalence and covariate shift.

### DA-12 — Hashes and chains do not establish truth, completeness, or immutable history

1. **Criticism:** A matching SHA-256 value shows consistency relative to the supplied digest; a self-contained chain can be rewritten in full, and removing a valid tail may leave a valid prefix. Neither property proves that the recorded event was true or that no record is missing.
2. **Evidence:** [TRUST_AND_SECURITY_ASSUMPTIONS.md](../security/TRUST_AND_SECURITY_ASSUMPTIONS.md) describes the local chain as tamper-evidence, not distributed immutability, and documents tail deletion. [PROTOCOL_VERSIONING.md](../cryptography/PROTOCOL_VERSIONING.md) says package hashes need a trusted expected hash/checkpoint.
3. **Severity:** High for claims of immutable, complete, or independently witnessed evidence.
4. **Current mitigation:** The repository implements canonical serialization, SHA-256 chain checks, an independent offline verifier, and tests for selected tampering cases. Documentation explicitly rejects blockchain/distributed-immutability claims.
5. **Remaining uncertainty:** There is no automatic external append-only witness/checkpoint in the described local architecture; the cited tests cover a finite set of mutations.
6. **Experiment that could resolve it:** Run an adversarial completeness test that deletes prefixes, tails, interior records, duplicates/reorders entries, and rewrites the entire chain; show which cases are detected with and without an externally stored signed tip. Establish and test an independent checkpointing process before claiming completeness.

### DA-13 — Demo key custody does not establish signer identity

1. **Criticism:** A signature can verify under an attacker-generated key if the artifact carries that key and no external fingerprint is pinned. A readable local private key permits forged replacement signatures.
2. **Evidence:** [notary.py](../../backend/app/cryptography/notary.py) stores an unencrypted demo private key under `results/notary/` and exports the public key in each artifact. [PROTOCOL_VERSIONING.md](../cryptography/PROTOCOL_VERSIONING.md) states that the embedded public key does not authenticate operator identity and that envelope metadata is not in the signed payload.
3. **Severity:** High for attribution/non-repudiation claims; medium for internal signature consistency.
4. **Current mitigation:** The notary is labeled a demo/research implementation; signature verification and fingerprint comparison are implemented, and the trust assumptions recommend obtaining the fingerprint independently.
5. **Remaining uncertainty:** Deployment-specific key access, rotation, backup, revocation, and compromise detection are not established by repository-level verification.
6. **Experiment that could resolve it:** Conduct a key-custody tabletop and access-control test; verify that a separate recipient rejects a correctly signed artifact from an unpinned key, accepts the pinned key, and detects rotation/revocation policy changes. For operational use, test an externally controlled signer or KMS/HSM integration.

### DA-14 — Timestamps are metadata, not trusted time

1. **Criticism:** A timestamp produced by the application host can be wrong or changed; a signature that does not cover the timestamp cannot prove that signing occurred at the represented time.
2. **Evidence:** [PROTOCOL_VERSIONING.md](../cryptography/PROTOCOL_VERSIONING.md) states that protocol-v1 signatures cover the payload digest only and do not bind `signed_at`; [TRUST_AND_SECURITY_ASSUMPTIONS.md](../security/TRUST_AND_SECURITY_ASSUMPTIONS.md) says host/database/file timestamps are not independently trusted.
3. **Severity:** Medium for chronology claims; high where a legal or incident-response claim depends on time of creation.
4. **Current mitigation:** The code and docs describe timestamps as descriptive, and temporal checks detect selected inconsistencies rather than claiming trusted UTC time.
5. **Remaining uncertainty:** Clock synchronization, drift, and host time source are deployment properties not established by the repository.
6. **Experiment that could resolve it:** Test clock rollback/skew/tampering behavior and ensure chronology claims are rejected or marked untrusted; if trusted time is required, obtain and verify an external timestamp token over the digest.

### DA-15 — Reproduction instructions do not freeze the Python environment or external inputs

1. **Criticism:** Fixed random seeds and a commit ID are insufficient for complete reproducibility when dependency resolution, platform/runtime versions, hardware, external data, or implementation nondeterminism can vary.
2. **Evidence:** [INDEPENDENT_REPRODUCTION_PROTOCOL.md](./INDEPENDENT_REPRODUCTION_PROTOCOL.md) says Python dependencies are minimum-version ranges and asks researchers to record a resolved environment. [SUPPLY_CHAIN_SECURITY.md](../security/SUPPLY_CHAIN_SECURITY.md) confirms there is no Python resolver lockfile; the frontend has a committed npm lockfile.
3. **Severity:** High for byte-identical reproduction; medium for reproducing broad qualitative outcomes.
4. **Current mitigation:** The protocol directs researchers to retain commit, dirty status, package versions, dataset hashes, platform/hardware, configuration, and verifier output. Experiments record seeds/configuration where applicable.
5. **Remaining uncertainty:** A later install can resolve different Python dependencies, and external dataset availability/license/checksum may vary. Runtime determinism across machines is not guaranteed.
6. **Experiment that could resolve it:** Have an independent researcher reproduce a named experiment in a clean environment from a pinned commit, retain the exact resolved environment/container digest and raw package, and compare declared tolerances for metrics and artifacts. Record every deviation and failure.

### DA-16 — The ablation is a component-cost study, not proof of improved prediction

1. **Criticism:** A–E arms reuse one model, holdout, predictions, and probabilities per trial. Consequently, post-prediction XAI/evidence cannot improve predictive metrics in this design; interpreting equal or changed metrics as a causal accuracy benefit would be invalid.
2. **Evidence:** [ABLATION_STUDY.md](./ABLATION_STUDY.md) specifies shared predictions and explicitly says non-zero predictive deltas indicate a defect or changed measurement. It excludes model fitting from arm-specific cost and says the benchmark does not use the production database/API/signing path.
3. **Severity:** Medium; high if the result is advertised as demonstrating predictive gains from XAI or cryptography.
4. **Current mitigation:** Arm semantics, measured costs, non-applicable values, and the expected zero predictive delta are documented; tests check pairing and applicable costs.
5. **Remaining uncertainty:** Costs may differ materially in end-to-end deployment due to concurrency, database persistence, filesystem, network, API serialization, and signing-key operations omitted from this benchmark.
6. **Experiment that could resolve it:** Keep the current paired experiment for component cost, then run a separately designed end-to-end load study against the deployed API/database with realistic traffic rates, randomized arm/order where applicable, process RSS, storage accounting, p50/p95/p99 latency, and fault/load conditions.

### DA-17 — Bootstrap intervals may be unstable or describe only configured runs

1. **Criticism:** With few trials, bootstrap intervals are coarse and sensitive to the trial-generating design. Repeating seeds on one synthetic generator does not create independent evidence about a target population.
2. **Evidence:** [STATISTICAL_METHODOLOGY.md](./STATISTICAL_METHODOLOGY.md) documents EXP-F's three default repeats, paired percentile bootstrap, and caveat that few or correlated trials do not justify population-level conclusions. [statistical_analysis.py](../../backend/app/ml/evaluation/statistical_analysis.py) resamples trial-level observations and does not emit p-values.
3. **Severity:** High for population inference; medium for descriptive configured-run variability.
4. **Current mitigation:** Method selection is design-explicit; raw observations, IDs, digests, resample counts, seeds, variance, and limitations are attached; no p-values or automatic significance claims are produced.
5. **Remaining uncertainty:** The number and independence of trials needed for stable estimates on a target population are not established. Bootstrap calculations cannot repair a biased sampling frame.
6. **Experiment that could resolve it:** Predefine the estimand and sampling unit, conduct a pilot variance analysis, choose trial/sample counts prospectively, and validate interval coverage or stability via repeated independent collection units. Keep the raw data and design with each derived statistic.

### DA-18 — Performance measurements are scoped microbenchmarks, not end-to-end service costs

1. **Criticism:** Reported latency and memory figures depend on machine state, execution order, and measurement boundaries. Python `tracemalloc` does not capture all native allocations; serialized record size is not database or filesystem storage.
2. **Evidence:** [ABLATION_STUDY.md](./ABLATION_STUDY.md) specifies median timings, excludes model fitting and production API/database/network work, notes possible undercounting of native memory, and limits storage to compact JSON representations. It also states cost summaries are descriptive, with no randomized execution order.
3. **Severity:** Medium for interpretation of current measurements; high if presented as production SLA or total overhead.
4. **Current mitigation:** The exact scope/semantics and excluded overhead are documented; unavailable metrics are null rather than represented as measured zero.
5. **Remaining uncertainty:** No controlled multi-machine/load study establishes repeatability or operational tail latency/resource use.
6. **Experiment that could resolve it:** Run a preregistered service-level benchmark on a recorded hardware/software stack, randomize component/run order, warm up consistently, measure process RSS and disk/database growth, and report distributions and confidence intervals across independent sessions.

### DA-19 — Local security controls do not create a secure multi-user or hostile-host boundary

1. **Criticism:** Validation, CORS, demo-mode restrictions, integrity checks, and path handling do not substitute for identity, authorization, resource isolation, or protection from a privileged host/database writer.
2. **Evidence:** [TRUST_AND_SECURITY_ASSUMPTIONS.md](../security/TRUST_AND_SECURITY_ASSUMPTIONS.md) says the API does not establish general authentication/RBAC and that host compromise can affect state. [registry.py](../../backend/app/ml/registry.py) loads model artifacts with `joblib` and preprocessing artifacts with `pickle`, which must not be treated as safe for untrusted files. The [platform threat model](../security/SENTINELCRYPT_PLATFORM_THREAT_MODEL.md) covers resource exhaustion and serialized artifact risk.
3. **Severity:** Critical for public or multi-user deployment; high for any integrity assertion under host compromise.
4. **Current mitigation:** Upload schemas, size/type/path controls, generated storage names, tests, an integrity auditor, and extensive scope disclaimers mitigate selected cases. Public deployment is not represented as safe.
5. **Remaining uncertainty:** The actual deployment's network reachability, authentication gateway, OS permissions, quotas, backup isolation, and artifact provenance are unknown. Unit tests cannot prove these properties.
6. **Experiment that could resolve it:** Perform a deployment-specific security assessment: enumerate exposed routes, test authorization/object-level access and resource limits, validate worker isolation and artifact digest-before-deserialization policy, and attempt database/filesystem/key modification with least-privileged and administrator accounts. Do not expose the service publicly until the required controls pass.

### DA-20 — External validity and novelty are not established by a repository-only literature frame

1. **Criticism:** Combining ML, SHAP, and hash-linked evidence is not by itself a novel research contribution, and the repository's current synthetic experiments do not establish that the approach improves actual security decisions in operational contexts.
2. **Evidence:** [RESEARCH_PROPOSAL.md](./RESEARCH_PROPOSAL.md) explicitly says novelty must be established through literature review rather than assumed. [LITERATURE_REVIEW.md](./LITERATURE_REVIEW.md) contains search questions and an empty evidence table template rather than a completed systematic synthesis. The [claims registry](./RESEARCH_CLAIMS_REGISTRY.md) distinguishes tested synthetic results from untested real-data claims.
3. **Severity:** High for publication-level novelty or external-validity claims; low for describing SentinelCrypt as a research prototype.
4. **Current mitigation:** Project documents caution against “first” or novelty-by-combination claims and maintain a claim status registry with counter-evidence and limitations.
5. **Remaining uncertainty:** The literature scope, search date, inclusion criteria, related-system comparison, and a distinct contribution beyond integration are not established by the inspected repository evidence.
6. **Experiment that could resolve it:** Conduct and publish a reproducible systematic or scoping review with databases, dated queries, inclusion/exclusion criteria, and a comparison matrix. Separately define a falsifiable contribution claim and test whether a workflow-level benefit remains over simpler logging or independent verification baselines.

## Overall assessment

The strongest claims presently supported by the repository are bounded engineering claims: that the prototype implements selected ML/XAI/evidence workflows; that selected synthetic experiments and controlled mutation tests execute; and that the offline verifier can check specified package properties under its supported versions. Those claims do not establish real-world IDS efficacy, real cross-dataset generalization, causal explanation validity, universal tamper detection, trusted time, signer identity without a pinned key, or production security.

The project already discloses many of these boundaries. The main scientific risk is not necessarily that a specific measured result is wrong; it is that a reader may generalize a controlled synthetic or internal-consistency result beyond its design. Any external paper, demo, or dashboard should preserve the dataset, sampling, benchmark, and cryptographic qualifications from this report.

## Suggested order of work

1. Establish authorized real-data and capture-group/time-separated evaluation before making efficacy/generalization claims.
2. Define a target operational sampling frame, prevalence, and decision costs.
3. Independently reproduce key experiments with a pinned environment and raw-data preservation.
4. Evaluate end-to-end performance and security under the intended deployment model.
5. Anchor signer identity, package completeness, and chronology outside the application host where those properties matter.
6. Complete the literature review before asserting novelty.

This report adds no security or ML guarantee and does not replace experiment-specific preregistration, peer review, or deployment threat assessment.
