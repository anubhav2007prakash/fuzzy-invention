# SentinelCrypt AI — Experiment Design

## A — Cross-Dataset Generalization
**Question:** How does performance change across compatible independent datasets?

**Variables:** training dataset, evaluation dataset, model, preprocessing.

**Metrics:** macro-F1, per-class recall/precision, confusion matrix, PR-AUC where appropriate.

**Control:** fixed seeds, explicit feature mapping, consistent evaluation definitions.

## B — Explanation Stability
**Question:** How stable are feature attributions under controlled perturbations?

**Metrics:** cosine similarity, rank correlation, top-k overlap, prediction consistency.

## C — Ledger Integrity & Overhead
**Question:** Can controlled modifications be detected and what verification overhead occurs?

**Mutations:** payload, previous hash, deletion, insertion, reorder.

**Metrics:** detection rate, verification time, throughput, storage overhead.

## D — Model Comparison
Compare Logistic Regression and Random Forest under the same protocol.

## Reproducibility
Record dataset hash, code commit, preprocessing version, seed, model configuration, software versions, experiment ID, output hash.

## Statistical Reporting
Where sample size allows, report distributions and uncertainty rather than relying on one run.
