# SentinelCrypt AI — ML Methodology & Model Card

## Objective
Evaluate baseline ML models for network intrusion classification under reproducible protocols.

## Baselines
**Logistic Regression:** linear baseline.

**Random Forest:** nonlinear tree-based baseline.

## Metrics
Accuracy, precision, recall, F1, macro-F1, weighted-F1, confusion matrix, and ROC-AUC/PR-AUC where appropriate.

For imbalanced data, emphasize class-wise and macro metrics rather than accuracy alone.

## Model Card
**Model:** [version]
**Algorithm:** [algorithm]
**Dataset:** [dataset/version]
**Features:** [schema]
**Preprocessing:** [pipeline]
**Seed:** [seed]
**Metrics:** [results]
**Intended use:** controlled research
**Out-of-scope:** production security decisions without independent validation
**Limitations:** dataset shift, imbalance, benchmark limitations.

## Reproducibility
Record environment versions, dataset hash, preprocessing version, seed, configuration, and artifact checksum.
