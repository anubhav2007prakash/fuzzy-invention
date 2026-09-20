# SentinelCrypt AI — Threat Model & STRIDE

## Assets
Dataset provenance, model artifacts, prediction records, explanations, audit records, experiment results, configuration.

## STRIDE
| Threat | Example | Mitigation |
|---|---|---|
| Spoofing | Unauthorized remote API user | Authentication before remote deployment |
| Tampering | Modified audit record | Hash-chain verification |
| Repudiation | Disputed experiment configuration | Versioned metadata and future signed exports |
| Information Disclosure | Stack trace leaks | Safe errors |
| Denial of Service | Oversized batch | Limits/rate limiting |
| Elevation of Privilege | Excess admin access | Least privilege |

## ML Threats
Data leakage, label leakage, dataset shift, class imbalance, overfitting, misleading confidence, explanation instability.

## Ledger Threat Model
The chain detects changes relative to the trusted verification process. It does not protect against a fully compromised host that can replace both stored data and trusted verification code.

## Assumptions
Authorized datasets; controlled environment; trusted standard crypto library; no hostile application code.

## Abuse Prevention
No features for exploitation, credential theft, malware delivery, or unauthorized scanning. Testing remains local, synthetic, or explicitly authorized.
