# SentinelCrypt AI — DFD & UML Design

## Context DFD
```text
Researcher
    |
Dashboard
    |
SentinelCrypt API
 |       |        |
ML     Audit   Experiments
 |       |        |
Models Database Results
```

## Level-1 Flow
Dataset → validation/provenance → preprocessing → model → prediction → explanation → canonical evidence → ledger → verification.

## Prediction Sequence
```text
Researcher -> API: POST /predict
API -> PredictionService: validate
PredictionService -> Model: infer
PredictionService -> XAI: explain
PredictionService -> AuditLedger: append
AuditLedger -> DB: persist
API -> Researcher: result
```

## Verification Sequence
```text
Researcher -> API: verify
API -> Ledger: verify()
Ledger -> DB: read ordered records
Ledger -> Ledger: recompute
Ledger -> API: status
API -> Researcher: result
```

## Relationships
Dataset 1—N Model; Model 1—N Prediction; Prediction 1—0..1 Explanation; Prediction 1—1 AuditRecord; Experiment 1—N evaluations.

Implement final diagrams in Mermaid/draw.io and store them in `docs/diagrams/`.
