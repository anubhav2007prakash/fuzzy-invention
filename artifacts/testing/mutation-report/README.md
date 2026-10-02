This directory holds checked-in historical context and CI-generated mutation
reports. The CI workflow overwrites `mutation-report.json` for each run and
uploads the directory as a workflow artifact. The historical crypto-only
measurement is retained separately and is not a baseline for the corrected
runner; see `docs/testing/MUTATION_TESTING.md`.
