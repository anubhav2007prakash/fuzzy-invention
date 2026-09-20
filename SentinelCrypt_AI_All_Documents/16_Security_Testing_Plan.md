# SentinelCrypt AI — Security Testing Plan

## Objectives
Verify safe handling of malformed input and reliable detection of controlled ledger modifications.

## Test Areas
**API:** malformed JSON, missing fields, wrong types, oversized batch, invalid IDs, unsupported files.

**Audit:** payload/hash/link mutation, deletion, insertion, reordering.

**ML/Data:** missing features, wrong types, NaN/infinite values, incompatible model versions, leakage checks.

**Dependencies:** vulnerability review/scanning before release.

## Pass Criteria
Expected invalid inputs produce structured errors. Every documented ledger mutation is detected.

## Regression Suite
Automate canonicalization, hashing, verification, input validation, and artifact metadata tests.

## Safety
Use local fixtures and authorized public datasets only.
