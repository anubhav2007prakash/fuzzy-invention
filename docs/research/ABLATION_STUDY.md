# SentinelCrypt Ablation Study (EXP-F)

## Purpose

EXP-F measures the predictive results and operational costs of adding explainability, cryptographic evidence, and the experiment-provenance envelope to a common ML pipeline. It is a measurement framework, not a claim that an added component improves SentinelCrypt. In particular, the XAI and evidence stages run after prediction and must not change the model's predictions.

## Arms

| Arm | Configuration |
|---|---|
| A | ML only |
| B | ML + XAI |
| C | ML + cryptographic evidence |
| D | ML + XAI + cryptographic evidence |
| E | Full SentinelCrypt benchmark path: D plus a hashed experiment-lineage manifest |

All arms include CSV dataset validation, preprocessing, model fitting, and inference. The synthetic frame is serialized to CSV and checked by the application's dataset validator before any model work. Preprocessing is fitted on the training partition only and reused for the held-out partition. It is not ablated: doing so would change the input distribution and confound the requested component comparison. E's manifest models the ordered raw dataset → validated dataset → processed dataset → training configuration → model → prediction → explanation → experiment → results → report lineage in this synthetic benchmark. It is not a claim that the benchmark created all of the production platform's corresponding persisted artifacts.

Legacy labels `full`, `no_xai`, and `no_evidence` are accepted as input aliases for E, C, and B respectively. The former `no_preprocessing` and `no_calibration` arms are not mapped: the current design deliberately keeps shared preprocessing and does not vary calibration, so mapping those labels would misrepresent the experiment. Results are emitted using A–E keys only. The old `results/exp_f_ablation.json` file is retained as historical output; new runs write `results/exp_f_ablation_v2.json`.

## Experimental protocol

- The dataset is the repository's generated synthetic network-flow dataset. It is not a real-world efficacy or generalization study.
- Each repeat uses a deterministic stratified 75/25 train/test split with seed `random_state + repeat_index`.
- Each repeat fits one classifier. All selected arms within that repeat reuse exactly the same fitted model, held-out data, predictions, and probabilities. This paired design isolates post-prediction component cost and prevents the arms from receiving different predictive outcomes.
- `model_type` is either `random_forest` or `logistic_regression`; default is random forest. Defaults are three repeats, 1,200 synthetic rows, and one explained held-out example per XAI arm and repeat.
- Model-fitting time is intentionally not attributed to one arm: model fitting occurs once and is shared. Inference and component-stage costs are reported separately.
- A failed explanation or failed evidence verification fails the experiment with an explicit error. The framework does not turn component failures into success-shaped missing values.

## Reported measurements

### Predictive quality

Per arm, the report contains precision, recall, F1, macro-F1, and average-precision PR-AUC (`pr_auc`), plus the shared helper's accuracy, ROC-AUC, ECE, and Brier score. Metric values are means across repeats; `metrics_ci95` contains 95% percentile-bootstrap intervals of trial-level means based on 2,000 resamples. Each summary identifies its raw runs, trial observations, and canonical-observation SHA-256 digest. Paired per-metric comparisons include paired bootstrap intervals and Cohen's dz, with raw trial IDs and a digest, against A and, when selected, E.

Since each arm shares a model and predictions within each repeat, predictive deltas should be zero. A non-zero delta is a test/implementation defect or a change in what is being measured—not evidence that XAI or cryptographic recording improved classification.

### System cost

Each arm reports per-repeat observations and a trial-level bootstrap summary (mean, sample standard deviation, range, and 95% interval where at least two measurements exist):

- **Inference latency:** median of three predictions over the full test set, divided by test rows (milliseconds per sample).
- **Explanation latency:** median `SHAPExplainer.explain()` latency per explained sample. Explainer-construction time is separate. Both are not applicable to A and C.
- **Evidence-generation latency:** elapsed time to construct canonical prediction payloads and forward-linked SHA-256 record hashes and serialize their record-size representation. Not applicable to A and B.
- **Verification latency:** elapsed `verify_ledger` time over the complete generated evidence chain. Not applicable to A and B. The report also records whether verification succeeded and how many records it checked.
- **Peak traced memory:** largest isolated Python `tracemalloc` peak among inference, explanation, and evidence-generation/verification operations for the arm. The experiment excludes dataset validation, preprocessing, and model fitting from this metric; native allocations (for example, NumPy or model-library buffers) may be undercounted. This is not total process RSS.
- **Storage:** UTF-8 bytes in compact JSON audit-record representations (including the canonical payload) plus lineage-manifest entries for E. It excludes database row/index overhead, filesystem allocation, model files, and external storage. A and B report zero because this scoped evidence-artifact storage is not generated.

Unavailable component measurements have zero observations and null summary values; zero is reserved for measured zero cost, not “not applicable.” Cost summaries are descriptive per-arm summaries only; no timing difference is interpreted as a paired causal effect because execution order and measurement conditions are not randomized.

## Output and interpretation

The EXP-F response retains the normal experiment envelope and contains:

- `metrics.variants.A` through `.E`: configuration, per-arm mean metrics, confidence summaries, performance summaries, and raw per-repeat observations.
- `metrics.deltas_vs_A` and `metrics.deltas_vs_E`: mean predictive-metric differences when the relevant reference arm was run.
- `metrics.paired_deltas_vs_A` and `metrics.paired_deltas_vs_E`: paired per-repeat summaries.
- `metrics.performance_semantics`: definitions and measurement limits for cost fields.

The exact design assumptions, formulas, small-sample caveats, and raw-data
traceability format are documented in
[`STATISTICAL_METHODOLOGY.md`](./STATISTICAL_METHODOLOGY.md).

The EXP-F dashboard presents predictive metrics alongside XAI/evidence latency, memory, and storage. A blank component latency means the arm does not run that component; it does not mean a measured zero.

The result is bound to the experiment envelope's SHA-256 result hash. This local hash is an integrity check, not a signature, external timestamp, or distributed immutability guarantee. SHAP explanation latency is for the explicitly configured sample count; it must not be presented as a complete-dataset explanation cost unless that count covers every held-out row.

When an arm enables both XAI and evidence, the first representative explanation is attached to the first evidence record. If `explanation_samples` is greater than one, the other explanations contribute to latency/memory measurement but are not serialized into the evidence chain.

The generated chain is a controlled, in-process benchmark artifact. It does not generate signing keys or signatures, write to the production database, or measure production API, filesystem, frontend, or network overhead.

## Validation

`backend/tests/unit/test_new_experiments.py` verifies the A–E definitions; required predictive and system metrics; applicable/not-applicable costs; successful evidence verification; paired repeated predictions; input validation; and result persistence. Runtime and storage results remain machine-, dependency-, and configuration-specific. Compare repeated runs on the same controlled environment before drawing operational conclusions.
