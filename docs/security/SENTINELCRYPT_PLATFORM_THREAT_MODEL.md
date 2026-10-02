# SentinelCrypt Platform Threat Model

**Status:** Architecture security assessment  
**Scope:** SentinelCrypt application platform itself (not the network-intrusion detection domain model)  
**Assessment basis:** Repository implementation, configuration, migrations, tests, workflows, and checked-in research artifacts

## 1. Executive summary

SentinelCrypt is a research-oriented FastAPI and React application that ingests CSV datasets, trains and evaluates scikit-learn models, produces SHAP/XAI evidence, records prediction evidence in a forward-linked audit ledger, and exports reproducibility and research artifacts. SQLite/SQLAlchemy persistence and local filesystem storage are the current default deployment model. The application is explicitly described as a research prototype, and the repository contains demo-mode controls and extensive integrity tests, but it does not provide a complete production identity, authorization, key-management, or independently witnessed audit service.

The highest-impact residual risks are:

1. **Unauthenticated API and mode management:** repository-visible routes permit sensitive reads and high-impact mutations without an identity/authorization layer; the backend must not rely on frontend visibility or a caller-controlled mode switch.
2. **Trusted local execution and administrator/host compromise:** a process or operator with write access to the database, model files, results, or signing key can change both the evidence and the verifier inputs.
3. **Unsafe deserialization of model/preprocessing artifacts:** `joblib`/`pickle` loading is executable-code capable and must only consume trusted, integrity-verified artifacts.
4. **Notary trust-root weakness:** the demo Ed25519 private key is local, unencrypted, and the artifact carries its own public key; a key compromise can produce apparently valid replacement artifacts unless trust is anchored externally.
5. **Research-output freshness and consistency:** database rows, filesystem artifacts, experiment metadata, and frontend views can diverge without a transactional manifest or independent artifact registry.
6. **Availability and resource exhaustion:** CSV parsing, model training, SHAP explanation, and experiment execution are expensive and are exposed through API routes without a production-grade authenticated quota/sandbox boundary.

The cryptographic ledger detects many accidental or post-hoc modifications, including payload changes, broken links, gaps, and sequence changes. It is not a prevention mechanism and is not an independent append-only witness: an attacker controlling the host/database can delete or rewrite records and then alter the verification inputs or rebuild the chain.

## 2. System description and data flows

### Components

- **Frontend:** React/Vite single-page application in `frontend/src`; calls the versioned API and renders datasets, models, predictions, explanations, experiments, provenance, reviews, and audit status.
- **API/backend:** FastAPI application in `backend/app`; route modules under `api/v1` validate requests and invoke services.
- **Persistence:** SQLAlchemy models/repositories backed by SQLite by default (`sentinelcrypt.db`), with Alembic migrations. PostgreSQL is possible by configuration.
- **Filesystem stores:** `data/raw`, `data/processed`, `models/trained`, `models/artifacts`, and `results`.
- **ML pipeline:** CSV validation, preprocessing, training, evaluation, persisted model and preprocessing artifacts, prediction, and model selection.
- **XAI pipeline:** SHAP explanations, stability/agreement metrics, and explanation evidence.
- **Evidence/notary:** canonical JSON, SHA-256 payload/record hashes, forward hash chain, Merkle/research evidence helpers, and local Ed25519 signing in `results/notary`.
- **Experiment/research pipeline:** registered experiments, benchmark/challenge runners, provenance/reproducibility exports, reviews/collaboration, and notebooks/research artifacts.
- **CI/CD:** GitHub Actions workflows for CI, release, and security scanning; repository dependencies and build scripts.

### Representative flows

1. Client uploads CSV → filename/size checks → content hash/dataset validation → UUID-named raw file → dataset metadata and feature schema in DB.
2. Client requests training → dataset row/file read → preprocessing and model training → model/preprocessing artifacts on disk → model/evaluation metadata in DB.
3. Client requests prediction/explanation → DB metadata and artifacts loaded → result/evidence generated → audit record appended to the hash chain.
4. Client requests experiment/reproducibility export → experiment configuration/result and filesystem outputs are read → evidence package and optional notary signature are written.
5. Frontend reads API responses and renders status; it is not a trust boundary for integrity decisions.

## 3. Assets and security objectives

| Asset | Confidentiality | Integrity | Availability | Authenticity/non-repudiation |
|---|---|---|---|---|
| Uploaded/raw and processed datasets | May contain sensitive telemetry; protect by deployment policy | Hash, schema, provenance, and file/row correspondence | Parsing and training depend on availability | Source and content hash must be attributable |
| Dataset metadata and feature schemas | Moderate | Must match the bytes used by ML | Required for reproducibility | Registration identity |
| Trained models and preprocessing artifacts | High if proprietary | Must not be silently replaced | Required for inference/XAI | Model version and digest |
| Predictions and explanations | Potentially sensitive | Must correspond to model, dataset, and input | User-facing workflow | Evidence must be attributable |
| Audit records/hash chain | Moderate | Primary tamper-evidence asset | Verification/export must remain usable | Chain history and sequence |
| Notary private/public keys | Critical confidentiality for private key | Public key continuity | Signing/verification service | Signature trust root |
| Experiment configuration, metrics, notebooks, reports | Research/IP confidentiality | Reproducibility and provenance | Publication/reproduction | Author/time/version attribution |
| DB credentials and application configuration | Critical | Configuration integrity | Application startup | Deployment identity |
| Frontend/backend contract and displayed status | Low confidentiality | Users must not be misled | UI operation | API response authenticity |
| CI/CD workflows, dependencies, release artifacts | Supply-chain integrity | Build provenance | Delivery pipeline | Commit/build provenance |

## 4. Trust boundaries

1. **Internet/browser ↔ API:** request bodies, query/path values, multipart filenames, headers, and client-controlled configuration are untrusted.
2. **Frontend ↔ backend contract:** the browser is untrusted and may be stale, modified, or bypassed; backend validation is authoritative.
3. **API process ↔ database:** the service trusts DB records for metadata, but DB writes and direct DB access are higher-privilege operations.
4. **API process ↔ filesystem:** model, dataset, result, notebook, and key files are trusted only if ownership, path, permissions, and integrity are established.
5. **ML/XAI runtime ↔ serialized artifacts:** deserialization crosses a code-execution boundary; artifacts are not data-only.
6. **Application ↔ signing key:** the local notary key is a root of authenticity; compromise invalidates signatures issued by that key.
7. **Application ↔ external CI/dependency ecosystem:** packages, actions, base images, and build tools are supply-chain inputs.
8. **Research export ↔ external consumer:** exported JSON/CSV/plots/notebooks may be copied, modified, or replayed outside the application.
9. **Operator/admin ↔ all state:** administrators and host users can generally change DB, filesystem, configuration, dependencies, and keys; they are not a cryptographic trust boundary.

## 5. Attacker capabilities and assumptions

### In scope

- Unauthenticated or low-privilege API caller able to send malformed requests, upload files, invoke permitted routes, and read responses.
- Malicious dataset author able to control CSV bytes, column names, values, row counts, labels, and multipart filename.
- Research collaborator able to submit experiment configuration or metadata through supported routes.
- User with read/write access to the application database or artifact directories.
- Compromised administrator, host, CI runner, package registry dependency, or browser.
- Attacker able to replay, delete, reorder, duplicate, or replace exported research artifacts.

### Out of scope or not evidenced

- Breaking SHA-256 or Ed25519 cryptography.
- Exploiting the network-intrusion detector's statistical/model weaknesses as a separate domain threat.
- A remote database exploit independent of the application unless the deployment exposes the DB.
- Browser sandbox compromise or operating-system kernel exploitation.

## 6. Attack surfaces

- FastAPI routes: dataset upload/preview, training, prediction, explanations, audit list/status/verify/export, experiments, benchmark/challenge, research, reviews, collaboration, and mode switching.
- Multipart upload content, filename, form fields, JSON bodies, path/query parameters, and pagination/range parameters.
- CSV parser and dataframe operations; malformed encodings, oversized rows, pathological dimensions, NaN/Infinity, duplicate columns, and malicious labels.
- Local path construction for raw datasets, model artifacts, preprocessing artifacts, result packages, and notary files.
- SQLite/SQLAlchemy repositories, migrations, uniqueness constraints, and concurrent append behavior.
- `joblib.load` and `pickle.load` model/pipeline deserialization.
- Hash canonicalization, hash-chain verification, Merkle/evidence export, and Ed25519 signing/verification.
- Frontend API client, cached/stale bundles, permissive CORS configuration, and UI-only mode/read-only assumptions.
- GitHub Actions, package manifests/lockfiles, Docker build context, release artifacts, notebooks, and checked-in generated results.

## 7. Threat analysis

The table uses **Likelihood** and **Impact** as qualitative ratings for the current research deployment. “Existing mitigation” describes controls observed in the repository; “residual risk” remains after those controls.

| ID | Threat / scenario | Impact | Existing mitigation | Residual risk and recommended mitigation | Tests required |
|---|---|---|---|---|---|
| T-01 | Malicious dataset poisons labels/features or creates misleading evaluation results | Integrity, research validity, possible resource exhaustion | CSV/schema validation, size limit, SHA-256 deduplication, fixed seed, validation summaries | Valid data can still be malicious or distribution-shifted. Add provenance/approval, outlier/drift checks, immutable source manifest, bounded parser resources, and independent review | Poisoned labels, extreme values, duplicate rows, wide/long CSV, parser timeout/memory tests |
| T-02 | Corrupted dataset bytes or DB/file mismatch | Integrity, availability | Stored file hash, validation before save, UUID storage name, missing-file errors | Preview/training should re-hash and compare DB hash before use; fail closed on mismatch | Mutate raw bytes after registration; assert preview/training rejects mismatch |
| T-03 | Path traversal or absolute path in filename/metadata | Confidentiality/integrity | `validate_filename`, sanitized display name, UUID storage path, containment helper | Other DB-controlled paths and result/model paths need the same confinement check | `../`, `..\\`, drive paths, UNC paths, symlinks, null bytes, malicious extensions |
| T-04 | Malicious filename causes log/header/UI injection | Integrity/confusion | Filename sanitized for stored metadata; frontend rendering uses normal React values | Canonical display-name policy and length/control-character limits should be explicit | Unicode controls, CR/LF, very long names, HTML-like names |
| T-05 | Malformed API request or NaN/Infinity causes crash or inconsistent state | Availability/integrity | Pydantic/FastAPI validation, global malformed-input handlers, query bounds | Body size/rate limits and consistent error envelopes should be enforced at gateway and route level | Invalid JSON, wrong types, NaN/Infinity, oversized body, invalid UUID/ranges |
| T-06 | Database manipulation changes metadata, links, timestamps, or status | Integrity/authenticity | ORM constraints, migrations, verification endpoint | DB is a trusted local dependency; use least-privilege DB account, backups, migration checks, row/file digest reconciliation, and external audit sink | Direct tampering of each asset row; reconciliation detects mismatch |
| T-07 | Model artifact replacement or preprocessing artifact replacement | Integrity, arbitrary code execution, wrong predictions | Model type allowlist and missing/corrupt checks | `joblib`/`pickle` are executable deserialization. Store digest/signature, verify before load, confine paths, and load in isolated worker/container | Replace artifact with valid-looking/wrong model and malicious pickle; assert rejection/sandbox |
| T-08 | Experiment metadata/configuration manipulation | Research validity, reproducibility | Known experiment ID registry, configuration validation, generated packages | Bind config/result to commit, input hashes, dependency lock, and signed manifest; reject unknown fields where appropriate | Unknown/extra fields, changed parameters, stale result/config mismatch |
| T-09 | Audit record payload/hash/metadata manipulation | Evidence integrity | Canonical JSON and SHA-256 record hash; verifier checks payload and links | Local DB writer can alter all fields; add append-only external witness, DB permissions, and record signatures or periodic roots | Payload, previous hash, record hash, sequence, prediction link, timestamp mutations |
| T-10 | Record deletion | Evidence loss and gap | Strict sequence continuity detects missing middle records | Deletion after latest record may be invisible if no external expected count/root; use append-only storage, checkpoints, backups, and deletion alerts | Delete middle/first/last records; verify gap/root/checkpoint behavior |
| T-11 | Record reordering | Evidence ambiguity | Verifier sorts by sequence and checks continuity/links | Physical row order is not trusted; duplicate/changed sequence remains important. Add explicit unique/monotonic append checks and checkpoint anchoring | Shuffle query order; duplicate or alter sequence numbers; assert deterministic result |
| T-12 | Duplicate records | Double counting, inconsistent prediction/audit mapping | Unique sequence and prediction constraints in schema/migration | Enforce idempotency keys and duplicate payload detection at append boundary; test concurrent append | Duplicate sequence, prediction, same payload with new sequence, concurrent writes |
| T-13 | Signing-key compromise or arbitrary caller-selected signing | Forged research artifacts and loss of non-repudiation | Ed25519 signatures, fingerprint, private-file mode best effort, offline verifier; arbitrary `/notary/sign` is explicitly rejected, while stored experiment signing remains | Local unencrypted demo key and self-presented public key are not a production trust anchor. Use KMS/HSM, rotation/revocation, external trusted public-key distribution, and key custody separation | Arbitrary sign endpoint denial, key replacement, forged artifact with attacker key, rotation/revocation, fingerprint mismatch |
| T-14 | Compromised administrator or unauthenticated remote caller | Full confidentiality/integrity compromise, dataset/model deletion or poisoning, evidence forgery | Demo mode reduces accidental writes; backend guard is server-side; repository has no visible authentication/authorization boundary | Add authenticated principals, RBAC/object authorization, protected mode management, MFA for operators, approvals, immutable admin logs, and dual control for keys/evidence | Direct API access without UI, mode-switch authorization, per-resource authorization, and attributable admin actions |
| T-15 | Compromised host | All local assets can be read/changed | Some file permissions and containment checks | Host compromise defeats application-level assurances. Use hardened host/container, secret manager, read-only mounts, EDR, backups, and external evidence witness | Recovery/restore and post-compromise tamper-detection drills |
| T-16 | Compromised dependency/action/base image | Build/runtime compromise | Lockfiles/manifests and GitHub workflow definitions | Pin actions by immutable SHA, use dependency scanning/SBOM/signatures, isolated builds, review updates, and provenance attestations | CI policy tests reject floating actions/vulnerable dependency; reproducible build check |
| T-17 | Frontend/backend inconsistency or stale frontend | Misleading status, bypassed client restrictions | Backend demo-mode guard is authoritative; API versioning | Frontend should display server mode/version and never infer integrity from cached state; add contract/schema tests and cache invalidation | API/UI contract tests, stale bundle/version mismatch, direct API mutation in demo mode |
| T-18 | Timestamp manipulation or clock skew | Misordered evidence, misleading chronology | UTC-style notary timestamp and DB timestamps; sequence/hash chain is primary order | Timestamps are not trusted proof. Record server monotonic sequence, clock source/health, and signed timestamp context; reject client timestamps for evidence | Client timestamp ignored, clock skew, non-monotonic DB time, timezone formatting |
| T-19 | Stale artifacts/results replayed as current | Research and operational misdecision | Versioned filenames, experiment registry, provenance/reproducibility outputs | Bind result to dataset/model/config/dependency digests and creation commit; freshness policy and “stale” status in API/UI | Change source artifact after export; replay old package; assert stale marker/rejection |
| T-20 | Database inconsistency (partial commit, migration drift, orphaned files/rows) | Availability and evidence integrity | Alembic plus development `create_all` fallback, foreign keys/unique constraints | Migration failure fallback can mask drift; use fail-closed production startup, transactional workflows, reconciliation jobs, and backup verification | Inject migration failure, partial transaction, orphan file/row, schema drift |
| T-21 | Resource exhaustion through training, SHAP, experiments, or exports | Availability | Upload size and pagination bounds; demo read-only mode | Add authenticated quotas, job queue, timeouts, CPU/memory limits, cancellation, and isolated workers | Concurrent large jobs, SHAP timeout, export size, queue/backpressure tests |
| T-22 | Evidence export modified or replayed outside the server | Integrity/confusion | Canonical exports, hashes, optional signatures, offline verifier | Consumers must verify signature, trusted key fingerprint, input hashes, and protocol version; publish verification instructions and revocation state | Modify payload/signature/public key, protocol downgrade, replay old artifact |

## 8. Existing mitigations and their limits

### Strong controls observed

- Filename validation rejects traversal, absolute paths, null bytes, unsafe extensions, and suspicious dot prefixes.
- Dataset storage uses server-generated UUID names and verifies resolved containment.
- Upload size, pagination, UUID, experiment-ID, and many schema constraints are bounded.
- Demo mode applies a backend default-deny mutation guard; frontend restrictions are not relied upon.
- Canonical JSON plus SHA-256 payload/record hashing provides deterministic evidence.
- Ledger verification checks sequence gaps, previous-hash links, payload canonicalization, and record hashes.
- Database migrations define uniqueness for audit sequence/prediction and dataset file hashes.
- Notary artifacts include protocol version, digest, Ed25519 signature, public key, fingerprint, and verification result; the unsafe arbitrary-payload signing route is rejected and stored experiment signing is the supported path.
- Unit, integration, property, robustness, red-team, ledger, notary, provenance, reproducibility, and frontend tests already cover many expected cases.

### Important limitations

- The default configuration is development-oriented: SQLite, permissive local CORS origins, no visible user authentication/authorization layer, and a default secret rejected only for production/staging.
- Local filesystem/database state is treated as trusted by the application.
- `joblib`/`pickle` artifacts are executable inputs and are not a cryptographic trust boundary by themselves.
- The notary key is stored under the results directory with no external trust anchor or rotation/revocation protocol.
- Audit verification detects tampering in the records it receives; it cannot prove that a host has not deleted or replaced the entire ledger/database.
- CI workflow files shown in the repository contain checkout-only skeletons; security scanning and test execution must be confirmed in the effective workflow configuration.
- Research outputs and notebooks are valuable evidence but are not automatically immutable, signed, or independently witnessed.

## 9. Recommended security architecture

### Priority 0 — before production or untrusted multi-user use

1. Add real authentication, role-based authorization, CSRF strategy for browser sessions, and tenant/object authorization for every mutating and sensitive read route, including notary and mode-management routes. A caller must never be able to elevate the process from Demo Mode to Research Mode without an authorized operator identity.
2. Move signing to KMS/HSM or a dedicated notary service; distribute trusted public keys out-of-band; implement key rotation, revocation, and compromise recovery.
3. Treat all serialized ML artifacts as untrusted: verify a signed manifest and SHA-256 digest before loading, restrict artifact paths to configured roots, and load in an isolated worker with least privilege.
4. Use PostgreSQL (or an equivalent managed database) with least-privilege credentials, encrypted backups, migration fail-closed behavior, and transactional append/idempotency controls.
5. Add an independent append-only evidence sink or periodic externally witnessed Merkle roots/checkpoints.

### Priority 1 — integrity and availability hardening

1. Create a signed manifest tying dataset bytes, schema, model/preprocessing artifacts, code commit, dependency lock, experiment config, metrics, and timestamps together.
2. Re-hash datasets and artifacts at every use; mark records stale or fail closed on mismatch.
3. Add reconciliation jobs for DB rows ↔ files, orphan detection, migration/schema drift, and ledger checkpoint continuity.
4. Run training, SHAP, experiments, and exports as bounded jobs with queueing, timeouts, memory/CPU limits, cancellation, and audit events.
5. Replace broad production fallback behavior with explicit startup failure when migrations cannot be applied.
6. Pin GitHub Actions and base images by digest/SHA; generate SBOMs and provenance; scan dependencies and lockfile changes.

### Priority 2 — operational and user-facing controls

1. Show server-provided mode, API version, artifact status, and verification freshness in the frontend.
2. Keep client and server schemas generated or contract-tested; invalidate stale frontend bundles after API changes.
3. Centralize structured security/audit logging with request IDs, actor IDs, outcome, object IDs, and immutable export.
4. Document data classification, retention/deletion, incident response, key compromise response, and research artifact verification.

## 10. Test plan

### Automated security-control tests

- Filename/path: traversal variants, absolute/UNC paths, symlinks, null/control characters, extension bypasses, and containment after resolution.
- Dataset integrity: post-registration byte mutation, duplicate hash, malformed CSV, oversized input, formula-like values, extreme dimensions, and parser resource limits.
- API validation: malformed JSON, NaN/Infinity, wrong types, unknown fields, invalid UUIDs, range inversions, body/upload limits, and consistent status/error envelopes.
- Database integrity: uniqueness, foreign keys, transaction rollback, concurrent append/idempotency, migration drift, orphan reconciliation, and backup restore.
- Ledger: payload/previous-hash/record-hash mutation, missing first/middle/last record, sequence gaps/duplicates, reorder, replay, timestamp changes, and external checkpoint mismatch.
- Artifact security: wrong digest, wrong model type, path escape, stale artifact, malicious serialized payload, key replacement, signature tampering, protocol downgrade, rotation, and revocation.
- Experiment/reproducibility: config/result mismatch, unknown parameters, changed dependency/code/data hashes, stale package, duplicate run, and output path escape.
- Frontend/backend: contract snapshots, stale bundle/API version mismatch, demo-mode direct API mutation, and server-authoritative integrity status.
- CI/supply chain: action pinning, dependency vulnerability policy, SBOM/provenance generation, locked reproducible install, and secret scanning.

### Required verification gates

- Run the complete backend and frontend test suites on every change touching security controls.
- Run mutation/property tests for canonicalization, ledger verification, and path validation.
- Run an isolated deserialization test suite in a disposable worker/container.
- Perform restore-and-verify drills for database, raw data, models, results, and notary public-key material.
- Perform a manual threat-model review after adding new API routes, artifact types, plugins, or CI workflows.

## 11. Residual-risk acceptance

Until the Priority 0 controls are implemented, SentinelCrypt should be treated as a **single-operator research prototype**. Its hash chain and signatures provide useful tamper evidence for accidental corruption and honest-party exchange, but they do not provide strong non-repudiation against a compromised host, administrator, signing key, database, or dependency supply chain. Research consumers must verify artifacts independently and must not interpret a valid local signature as proof that the underlying experiment was honestly executed.

## 12. Review triggers

Reassess this threat model when any of the following changes:

- New API route, plugin, upload format, model framework, serialized artifact, or external integration.
- Authentication/authorization, multi-tenancy, deployment topology, or database engine changes.
- Hash-chain/notary protocol, key location, canonicalization, or export format changes.
- CI/CD workflow, dependency manager, base image, release process, or notebook execution policy changes.
- A security incident, data-integrity anomaly, signing-key event, or research reproducibility failure occurs.
