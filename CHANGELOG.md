# Changelog

All notable changes to **SentinelCrypt AI** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-10-02

First stable release of SentinelCrypt AI — a research-oriented network
intrusion detection platform combining machine learning, explainable AI (XAI),
and cryptographic evidence verification.

### Added

#### Core Platform
- **Phase 1 — Dataset Foundation**: schema validation, leakage-safe
  preprocessing pipeline, SQLAlchemy ORM models, and FastAPI `/api/v1/datasets`
  routes (19/19 tests passing)
- **Phase 2 — Machine Learning Engine**: `BaseDetector`, `LogisticRegression`,
  `RandomForest`, `ModelEvaluator`, `ModelRegistry`, `TrainingService`, and
  `/api/v1/models` routes (33/33 tests passing)
- **Phase 3 — Prediction Pipeline**: single/batch inference, RFC 8785 canonical
  evidence packaging, SHA-256 audit ledger anchoring (39/39 tests passing)
- **Phase 4 — Cryptographic Audit Ledger**: forward-linked SHA-256 hash chain,
  tamper detection engine, `/api/v1/audit` endpoints with full chain
  verification (49/49 tests passing)
- **Phase 5 — XAI Engine**: TreeSHAP / LinearSHAP explanation service,
  perturbation-based stability scoring, `/api/v1/explanations` routes
  (101/101 tests passing)
- **Phase 6+7 — React 18 Frontend & Research Benchmark Suite**: Vite dashboard
  with Alerts, Datasets, Models, Predictions, XAI Charts, Audit Ledger, and
  Research Benchmark pages (110/110 tests passing)

#### Security & Research Hardening
- File-path security: filename sanitisation, path traversal rejection,
  UUID-based server-side storage names, directory containment verification
- Alembic migration suite with full schema validation tests (upgrade, downgrade,
  round-trip)
- 19 cryptographic ledger security tests covering payload tampering, pointer
  modification, record deletion, duplicate detection, and empty/corrupted chains
- 10 data-leakage prevention tests verifying imputer/scaler/encoder fit
  strictly on training data
- 21 SHAP validation tests: local accuracy, feature name alignment, and
  edge-case handling
- Config validation: rejects default `SECRET_KEY` in production, validates
  `TRAIN_RATIO`, log levels, and upload-size minimums
- UUID format validation on all model/prediction/audit API endpoints
- Database indexes on `datasets.file_hash`, `experiments.dataset_id`,
  `experiments.status`, `audit_records.sequence_number`

#### Research Lab (Professor Mode)
- Research lab API endpoints: `/api/v1/research`, `/api/v1/benchmark`,
  `/api/v1/falsification`, `/api/v1/integrity`, `/api/v1/collaboration`,
  `/api/v1/review`
- Falsification lab with statistical test harness
- Benchmark suite with reproducible experiment runs (EXP-A through EXP-D)
- Independent evidence verifier and protocol versioning
- Research artifact lineage tracking (Merkle tree + notary)
- XAI agreement analysis across explanation methods
- Prediction calibration lab with reliability diagrams

#### Controlled Failure Injection Framework
- `backend/tests/failure_injection/` — isolated test-only framework
- **9 injectors**: `DatabaseUnavailableInjector`, `MissingModelArtifactInjector`,
  `CorruptedDatasetInjector`, `CorruptedAuditRecordInjector`,
  `SHAPFailureInjector`, `IncompleteExperimentInjector`,
  `MissingConfigurationInjector`, `UnavailableDependencyInjector`,
  `InvalidAPIResponseInjector`
- `SafeFailureAsserter` helpers: `assert_safe_fail`, `assert_meaningful_error`,
  `assert_no_silent_invalid_result`, `assert_no_existing_corruption`,
  `assert_consistent_state`
- Unit, chaos, and integration test suites for all injector types
- Verified: fails safely, reports meaningful errors, does not corrupt
  existing evidence, maintains consistent state

#### API Enhancements
- `GET /health/detailed` — DB connectivity, Alembic version, component counts,
  uptime, disk usage
- `GET /datasets/{id}/preview` — first N rows + per-column statistics
- `GET /audit/export` — ledger export as JSON or CSV with download headers
- Confidence threshold gating on `POST /predictions` with `UNCERTAIN` class
  support

#### Developer Tooling
- `Dockerfile.backend`, `frontend/Dockerfile`, `docker-compose.yml`
- `scripts/demo_golden_path.py` — end-to-end verification script
- `scripts/supply_chain.py` — SPDX SBOM generation, dependency licence
  inventory, checksum reports
- `scripts/sentinel_verify.py` — independent evidence verifier CLI
- `scripts/metamorphic_harness.py` — metamorphic relation test runner
- `scripts/mutation_harness.py` — mutation testing harness

#### CI/CD
- **CI workflow** (`ci.yml`): lint, unit tests, integration tests
- **Security Scan** (`security.yml`): Bandit + Safety static analysis
- **Supply Chain Security** (`supply-chain.yml`): Gitleaks history scan
  (with `.gitleaks.toml` allowlist), pip-audit, npm audit, SPDX SBOM
  generation, dependency licence inventory
- **Mutation workflow** (`mutation.yml`)

#### Documentation
- `docs/testing/CONTROLLED_FAILURE_INJECTION.md`
- `docs/testing/DIFFERENTIAL_TESTING.md`
- `docs/testing/METAMORPHIC_TESTING.md`
- `docs/testing/MUTATION_TESTING.md`
- `docs/testing/PROPERTY_BASED_TESTING.md`
- `docs/research/` — ablation study, falsification lab, calibration lab,
  robustness lab, statistical methodology, reproducible builds, research
  claims registry, independent reproduction protocol
- `docs/security/` — threat model, supply chain security, temporal integrity,
  trusted computing base, trust and security assumptions, release signing
- `docs/cryptography/` — protocol versioning, reference implementation,
  research artifact lineage, independent evidence verifier
- Full community health files: `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`,
  `LICENSE` (MIT + third-party notices), `SECURITY.md`
- `vercel.json` for Vite frontend deployment

### Fixed
- Alembic `sqlalchemy.url` removed from `alembic.ini` so `env.py` always
  reads `DATABASE_URL` — Docker volume DB previously got zero tables
- `docker-compose.yml` `DATABASE_URL` corrected to 4-slash absolute path
- Vite proxy rewritten: replaced broken `VITE_API_URL=http://backend:8000`
  with `VITE_PROXY_TARGET` env var; browser now resolves the backend correctly
- Dataset schema chips rendered feature objects as React children (crash) —
  fixed to render `feature_name`/`data_type` strings
- `fetchApi` guarantees `ApiError.message` is always a string (FastAPI detail
  envelopes are objects and blanked the page)
- Mobile layout: removed inline `grid-template-columns` so the `≤768px`
  media query wins correctly

### Security
- Removed `results/notary/notary_private_key.pem` from git tracking
  (was a throwaway test key; now gitignored)
- Added `.gitleaks.toml` to allowlist historical test key path
- Added `*.pem`, `*.key`, `*.db` patterns to `.gitignore`
- Removed `sentinelcrypt.db` from git tracking

---

## [Unreleased]

_No unreleased changes at this time._

---

[1.0.0]: https://github.com/anubhav2007prakash/fuzzy-invention/releases/tag/v1.0.0
