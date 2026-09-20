# SentinelCrypt AI — Software Requirements Specification

## 1. Functional Requirements
- **FR-01:** Register dataset name, source, version/date, file hash, dimensions, and label definition.
- **FR-02:** Validate required dataset fields before training.
- **FR-03:** Apply the configured preprocessing pipeline consistently.
- **FR-04:** Train Logistic Regression and Random Forest baselines.
- **FR-05:** Store training configuration, seed, preprocessing version, and metrics.
- **FR-06:** Reject prediction requests for unavailable model versions.
- **FR-07:** Validate prediction feature schemas.
- **FR-08:** Return predicted class and probability/confidence where supported.
- **FR-09:** Assign a unique prediction ID.
- **FR-10:** Associate explanations with predictions.
- **FR-11:** Record explainer/model/version metadata.
- **FR-12:** Canonicalize audit payloads.
- **FR-13:** Link each audit record to the previous record hash.
- **FR-14:** Calculate and store a SHA-256 digest.
- **FR-15:** Verification shall identify the first invalid link.
- **FR-16:** Experiments shall store configuration and results.

## 2. Non-Functional Requirements
| ID | Category | Requirement |
|---|---|---|
| NFR-01 | Reproducibility | Seeds/configuration recorded |
| NFR-02 | Security | Inputs validated and bounded |
| NFR-03 | Integrity | Verification deterministic |
| NFR-04 | Performance | Normal demo requests remain responsive |
| NFR-05 | Maintainability | Clear module boundaries |
| NFR-06 | Testability | Security-critical logic unit tested |
| NFR-07 | Usability | Results understandable to reviewers |
| NFR-08 | Traceability | Dataset→model→prediction→evidence linked |

## 3. Constraints
Public/authorized datasets only; controlled local testing; SQLite acceptable for MVP; no production SOC claim.

## 4. Error Handling
Return structured errors for invalid input and unavailable resources. Never expose stack traces, secrets, or filesystem details.
