# SentinelCrypt AI — Test Plan & Test Cases

## Levels
Unit → Integration → API → End-to-End → Security Regression.

## Critical Cases
| ID | Test | Expected |
|---|---|---|
| T-01 | Valid dataset registration | Metadata stored |
| T-02 | Missing required column | Validation error |
| T-03 | Model training | Artifact + metrics |
| T-04 | Valid prediction | Prediction returned |
| T-05 | Invalid feature type | Validation error |
| T-06 | Audit append | Hash stored |
| T-07 | Valid chain | PASS |
| T-08 | Payload mutation | FAIL |
| T-09 | Link mutation | FAIL |
| T-10 | Record deletion | FAIL |
| T-11 | Record reorder | FAIL |
| T-12 | Explanation | Attribution returned |
| T-13 | Reproducibility | Comparable documented result |
| T-14 | Error safety | No secrets/stack trace |

## Exit Criteria
All P0 tests pass; mutation tests pass; critical defects are closed; clean-environment reproduction succeeds.
