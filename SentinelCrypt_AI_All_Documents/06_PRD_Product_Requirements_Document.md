# SentinelCrypt AI — Product Requirements Document
**Version:** 1.0 | **Status:** Implementation Draft | **Date:** September 2026

## 1. Product Overview
SentinelCrypt AI is a research-oriented defensive cybersecurity platform combining machine-learning network intrusion detection, explainable AI (XAI), and a tamper-evident cryptographic audit ledger.

## 2. Problem
IDS prototypes often emphasize classification accuracy while giving less attention to explanation stability, cross-dataset generalization, and integrity of stored alert evidence.

## 3. Goals
1. Build reproducible IDS baselines.
2. Generate predictions and explanations.
3. Store prediction evidence in a SHA-256 hash-linked ledger.
4. Verify ledger integrity.
5. Run controlled research experiments.
6. Present results through a professional research dashboard.

## 4. Non-Goals
Unauthorized monitoring, exploitation, malware, live offensive testing, blockchain claims, or claims of a new cryptographic primitive.

## 5. Users
- Student researcher
- Faculty/research reviewer
- Developer/reviewer

## 6. Core Features
Dataset management, preprocessing, ML training/evaluation, prediction, XAI, audit ledger, verification, experiment tracking, dashboard, exports, reproducibility documentation.

## 7. Requirements
| ID | Requirement | Priority |
|---|---|---|
| PRD-01 | Register approved public IDS datasets | P0 |
| PRD-02 | Record provenance and file hash | P0 |
| PRD-03 | Train at least two baseline models | P0 |
| PRD-04 | Persist model configuration and metrics | P0 |
| PRD-05 | Generate prediction records | P0 |
| PRD-06 | Create hash-linked audit records | P0 |
| PRD-07 | Verify ledger integrity | P0 |
| PRD-08 | Display model metrics | P1 |
| PRD-09 | Display explanations | P1 |
| PRD-10 | Run research experiments | P1 |
| PRD-11 | Export results | P1 |
| PRD-12 | Provide reproducibility instructions | P0 |

## 8. Acceptance
A clean environment should be able to reproduce the baseline, make a prediction, generate an explanation, append evidence, verify an unchanged ledger, and detect a controlled mutation.

## 9. Research Positioning
The integration itself is not sufficient evidence of novelty. Research value must come from a precise question, defensible methodology, measurements, and limitations.
