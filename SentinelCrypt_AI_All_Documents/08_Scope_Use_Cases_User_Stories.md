# SentinelCrypt AI — Scope, Use Cases & User Stories

## Scope
### In Scope
Dataset provenance, preprocessing, baseline ML, evaluation, prediction, XAI, cryptographic evidence integrity, experiments, dashboard, testing, and reproducibility.

### Out of Scope
Unauthorized scanning, exploitation, malware deployment, live third-party traffic interception, and production SOC orchestration.

## Actors
Researcher; Faculty Reviewer; Local Administrator; Experiment Runner.

## Use Cases
### UC-01 Register Dataset
Validate authorized dataset → compute file hash → store provenance → make available for experiments.

### UC-02 Train Model
Select dataset/configuration → preprocess → train → evaluate → store artifact and metrics.

### UC-03 Analyze Prediction
Validate features → infer → generate explanation → create evidence → append audit record.

### UC-04 Verify Ledger
Load ordered records → recompute hashes → verify links → report status and first failure.

### UC-05 Run Experiment
Select dataset/model/configuration → execute → store metrics and configuration.

## User Stories
- As a researcher, I want dataset provenance so results can be reproduced.
- As a researcher, I want multiple baselines so conclusions are not tied to one algorithm.
- As a reviewer, I want class-wise metrics so accuracy is not the only evidence.
- As a researcher, I want explanation metadata so attribution results can be reviewed.
- As a reviewer, I want ledger verification so controlled tampering can be demonstrated.
- As a developer, I want automated integrity tests to prevent regressions.
