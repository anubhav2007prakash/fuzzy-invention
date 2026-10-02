# SentinelCrypt Trusted Computing Base

**Status:** Repository-grounded architecture assessment  
**Scope:** Components whose correctness or integrity must be trusted to support SentinelCrypt claims about predictions, evidence, verification, provenance, or reproducibility.  
**Audience:** Operators, developers, reviewers, and researchers assessing a SentinelCrypt deployment or evidence package.

This document complements [TRUST_AND_SECURITY_ASSUMPTIONS.md](./TRUST_AND_SECURITY_ASSUMPTIONS.md) and [SENTINELCRYPT_PLATFORM_THREAT_MODEL.md](./SENTINELCRYPT_PLATFORM_THREAT_MODEL.md). It identifies the smallest practical trusted computing base (TCB) for particular claims. There is no single TCB that applies equally to every claim.

## 1. Meaning of trust labels

| Label | Meaning in this document |
|---|---|
| **Trusted** | Correctness or control of this component is a direct assumption for the named claim. A compromise can invalidate that claim. “Trusted” is not a guarantee that the component is secure. |
| **Semi-trusted** | The component supplies evidence or an input that can be checked or corroborated, but the component alone is not a sufficient trust anchor. Its result must be treated as conditional. |
| **Untrusted** | The component or data may be controlled by a caller or external party. Validate, constrain, or independently verify it before relying on it. |

These labels are claim-specific. For example, the database is trusted by the running application to retrieve a model record, but is only semi-trusted evidence for an exported result if the recipient independently checks the package.

## 2. Architecture in scope

The repository currently includes:

- A React/Vite browser client in `frontend/`.
- A FastAPI API and service layer in `backend/app/`.
- SQLAlchemy persistence, SQLite by default, and Alembic migrations.
- Local filesystem storage for raw and processed datasets, model and preprocessing artifacts, results, and a demo notary key.
- Dataset validation, preprocessing, training, model evaluation, prediction, and SHAP/XAI code.
- Experiment and research execution, lineage metadata, a database integrity auditor, and audit records linked by a SHA-256 hash chain.
- Ed25519-signed research artifacts through the local notary implementation.
- `scripts/sentinel_verify.py`, a separate offline evidence-package verifier which does not import FastAPI or the SentinelCrypt application and does not access its database. Its base operation uses the Python standard library; Ed25519 verification requires the `cryptography` package.

Relevant implementation entry points include [the FastAPI application](../../backend/app/main.py), [database initialization](../../backend/app/db/database.py), [the model registry](../../backend/app/ml/registry.py), [lineage service](../../backend/app/services/lineage_service.py), [audit service](../../backend/app/services/audit_service.py), [cryptographic verifier](../../backend/app/cryptography/verifier.py), [notary](../../backend/app/cryptography/notary.py), [database integrity auditor](../../backend/app/research/integrity_audit.py), and [standalone verifier](../../scripts/sentinel_verify.py).

## 3. Trusted, semi-trusted, and untrusted component inventory

### Trusted for operation, subject to deployment controls

These components are part of the TCB whenever a claim depends on the running platform:

- **Deployed backend code and configuration:** API routes, schemas, validators, services, ML/XAI code, evidence generation, version handling, and the actual configuration loaded at runtime.
- **Runtime and cryptographic implementation:** the Python runtime, operating system, and installed cryptographic library used for signing or signature verification. The standalone verifier's own code and runtime are trusted for its verification result.
- **Host and process boundary:** the host account, filesystem permissions, process environment, and mechanisms used to deploy and run the application.
- **State stores for live operation:** the database and filesystem are trusted by the backend to return the records and bytes it reads. Their integrity is not independently established merely because the application reads them.
- **Signing-key custody:** the private Ed25519 key and the process allowed to use it are trusted for the claim that the signer controlled the key. The current notary is a local research/demo implementation, not a production key-management service.
- **Build and release path:** source revision, dependency resolution, build tooling, CI configuration, and release artifact transfer are trusted to the degree a deployed binary or package is attributed to SentinelCrypt.

### Semi-trusted: useful but not an independent anchor

- **Database rows and integrity-audit findings:** the integrity auditor performs read-only checks for selected relational and provenance invariants. A clean report does not prove that the database is complete, truthful, or unchanged by a sufficiently privileged actor.
- **Filesystem artifact bytes and stored digests:** comparing bytes with a digest detects mismatch relative to the expected digest. If an attacker can change both the artifact and the database/manifest digest, the comparison has no independent trust anchor.
- **Dataset validation, experiment manifests, model metadata, and lineage edges:** they describe what SentinelCrypt processed, but are generated or stored within the same application and state stores. They do not independently prove dataset origin, model behavior, or scientific validity.
- **The audit hash chain:** it detects many partial or accidental edits when the full expected record sequence is supplied. It is not independently append-only, and a complete rewrite or tail deletion can evade detection without an externally retained checkpoint.
- **Signed-artifact envelope and embedded public key:** digest and signature checks can establish internal consistency. A public key shipped only inside that same artifact does not establish the signer's real-world identity.
- **Host timestamps and artifact timestamps:** useful for recordkeeping but not a trusted time proof. Clock control, host compromise, or timestamp changes are outside the signature/time guarantees currently provided.
- **Frontend views and API responses:** convenient presentation of state. They do not independently validate the backend, database, or cryptographic result and must not be used as the only evidence for a security decision.
- **CI scan/build reports:** evidence about the exact commit and environment that ran them only when that association is verified. A scanner result is not a guarantee that dependencies are safe.

### Untrusted until validated or independently authenticated

- Browser code, browser storage, API callers, HTTP inputs, and all caller-supplied identifiers, paths, filenames, settings, and experiment parameters.
- Uploaded CSV content, including malformed, poisoned, mislabeled, or resource-exhausting datasets.
- Imported model, preprocessing, notebook, and other serialized artifacts. In particular, `joblib` and `pickle` loading is capable of executing code; a digest supplied by the same untrusted source does not make a file safe to deserialize.
- Externally obtained packages, build actions, containers, model/data artifacts, and research outputs until provenance and integrity are assessed.
- Self-reported or unanchored experiment metadata, Git revision strings, signer names, and timestamps.
- A signature's embedded public key when the question is “who signed this?” rather than “is this signature mathematically consistent with this key?”

## 4. TCB by security claim

### 4.1 Prediction integrity

**Claim to scope:** the returned prediction was computed by the expected SentinelCrypt code from the identified input using the intended model and preprocessing artifacts.

**Trusted:** deployed API and prediction/training code; input validation and preprocessing implementation; model and preprocessing files actually loaded; ML runtime and dependencies; operating system/process; and the database/filesystem mapping from model ID and dataset ID to those files.

**Semi-trusted:** model metadata, dataset hashes, lineage records, and prediction evidence persisted in the database. They can corroborate the result but are not an external authority when the same host controls both records and files.

**Untrusted:** client request and browser display, newly uploaded data, and externally supplied serialized artifacts.

**Limit:** this does not prove that the source dataset is representative or benign, that the model is scientifically valid, or that the prediction describes real-world certainty. For a stronger claim, independently preserve the input bytes, model/preprocessing hashes, code revision, configuration, and prediction output. Verify hashes before loading artifacts; do not deserialize an artifact from an untrusted source. Consider running training and inference in a restricted worker with no signing-key access and only the required data/artifact permissions.

### 4.2 Evidence integrity

**Claim to scope:** the supplied evidence package's covered bytes and internal relationships match their declared digests and evidence rules.

**Trusted:** the verifier implementation and runtime used to check the package; the cryptographic digest implementation; and the exact package bytes read by that verifier.

**Semi-trusted:** package manifest, file-hash list, lineage, and chain records. Their recomputed consistency detects changes only relative to what is included. A package can be internally valid yet incomplete, stale, misleading, or built from false inputs.

**Untrusted:** package contents until verification, and any external assertion that the package is the complete expected export unless corroborated.

**Limit:** completeness and freshness require an expected file inventory, record range, final chain hash, or package digest obtained and retained outside the package/host. A locally generated hash chain does not prevent its owner from replacing the chain.

### 4.3 Cryptographic verification

**Claim to scope:** a digest matches the signed payload and a signature verifies under a given public key.

**Trusted:** the independent verifier code; Python and SHA-256 implementation; `cryptography`/Ed25519 implementation when verifying signed envelopes; and the bytes selected as the verification input.

**Semi-trusted:** a public key/fingerprint embedded in the package. It supports self-consistency but not attribution. To assert SentinelCrypt operator identity, the recipient must obtain and pin the expected fingerprint from an independent trusted channel.

**Untrusted:** signer identity and timestamp claims not bound to a trusted key/time authority; an unpinned public key; and unsupported protocol versions.

**Limit:** signature validity proves control of the corresponding private key for the signed bytes, not correctness of the experiment, truth of metadata, secure key custody, or trusted signing time. The current local notary key is not a hardware-backed or externally governed trust service.

### 4.4 Experiment provenance

**Claim to scope:** a recorded experiment is traceable to declared data, configuration, model, code, and results.

**Trusted:** experiment runner and provenance-generation code; actual execution environment; code revision/build provenance; data and model bytes used; and the backend/database/filesystem at the time the run is recorded.

**Semi-trusted:** database experiment records, manifest fields, lineage graph, result hashes, and exported signatures. Internal consistency supports traceability but cannot on its own attest that all claims are true or that an artifact was not substituted before hashing.

**Untrusted:** experiment labels, self-reported authorship, user-provided configurations, and claims inferred only from the dashboard.

**Limit:** stronger provenance requires an independently verified build identity, immutable copies of inputs and outputs, externally retained hashes/checkpoints, and authenticated actor identity. The current deployment does not establish a general authenticated administrator or author identity.

### 4.5 Reproducibility

**Claim to scope:** another researcher can rerun the declared workflow and compare outcomes under a documented environment.

**Trusted:** source code/revision; dependency and runtime environment; dataset bytes and preprocessing; model/experiment configuration; random seed handling; hardware/runtime behavior where relevant; and the reproduction instructions.

**Semi-trusted:** environment manifests, fixed seeds, reported metrics, and evidence package. These help comparison but do not ensure bit-for-bit determinism or availability of external datasets/dependencies.

**Untrusted:** unverified downloads, undocumented local changes, and expectations that signed or hashed results must be scientifically correct.

**Limit:** a verifiable package is not a substitute for rerunning the experiment. Nondeterministic libraries, hardware, and external resources may prevent byte-identical results. Evidence can make declared outputs checkable without proving full scientific reproducibility.

## 5. Minimum practical TCB

The smallest TCB depends on the claim. Do not expand it by implication:

| Claim | Minimum practical TCB | Does not establish |
|---|---|---|
| “These package files match the declared hashes.” | Offline verifier code/runtime, SHA-256 implementation, package bytes, and hash manifest. | Package completeness, provenance, freshness, scientific correctness, signer identity. |
| “This signature is valid for these bytes under this key.” | Offline verifier, Ed25519 implementation, signed bytes, signature, and public key. | That the key belongs to the named operator unless its fingerprint is independently pinned. |
| “The audit chain provided here is internally consistent.” | Chain verifier, canonicalization/hash rules, complete supplied ordered records. | That records were never omitted or rewritten; completeness without an external tip/checkpoint. |
| “This prediction came from the declared model and preprocessing.” | Backend prediction path, ML/runtime dependencies, exact model/preprocessing/input bytes, and trusted mapping from identifiers to bytes. | Dataset quality, model validity, real-world confidence, or downstream outcome. |
| “This experiment is attributable and reproducible.” | Source/build identity, runner, dependency environment, raw input, configuration, model, and recorded outputs; independent provenance anchors for adversarial settings. | Scientific truth or guaranteed identical results across environments. |

For offline evidence review, `scripts/sentinel_verify.py` narrows the verifier TCB by avoiding imports from FastAPI, React, the database layer, and training code. This is a meaningful isolation boundary already present in the repository. It does not remove the verifier implementation/runtime or package inputs from the TCB, and signed-package verification still requires the optional cryptography implementation.

## 6. Practical TCB reduction without restructuring

Prioritize controls that reduce who or what must be trusted for a specific claim:

1. **Use the standalone offline verifier for exported packages.** Verify a copied package on a separate machine without the API, frontend, training runtime, or application database. Record verifier version, result, and package digest.
2. **Pin signer identity externally.** Publish/retain the expected notary public-key fingerprint through a separate controlled channel. Reject identity claims based solely on the artifact's embedded key.
3. **Retain independent checkpoints.** For audit completeness, periodically store the expected final sequence number and record hash—or a signed package digest—outside the SentinelCrypt host and its administrator's control. Compare it during verification.
4. **Separate signing from untrusted data processing operationally.** Keep the notary private key out of upload/training workers and use restrictive filesystem permissions and service identities. Do not allow untrusted model or preprocessing files to be loaded by a process with signing authority.
5. **Verify artifact digests before deserialization.** Resolve model/preprocessing artifact identity and expected digest from a separately protected manifest or trusted release record, then verify before `joblib`/`pickle` loading. A digest stored beside a mutable artifact on the same writable host is only defense against accidental corruption.
6. **Minimize write authority.** Use distinct OS/database permissions for API operation, training, signing, backup, and read-only verification where deployment permits. A verifier should consume a read-only evidence copy and need no database credentials.
7. **Bind claims to reviewed build identity.** Preserve the commit SHA, dependency lock/SBOM, build output digest, and CI result for the deployed version. Verify the association rather than trusting a branch name or a mutable CI status page.
8. **Treat database integrity audit as detection, not containment.** Run the read-only integrity audit against a consistent backup/snapshot when possible, preserve the report externally, and investigate findings. Do not treat “clean” as proof against a privileged database writer.
9. **Keep the browser outside integrity decisions.** Use API and offline-verifier outputs for verification; the dashboard should remain a view, not the trust authority.

These are deployment/process controls that can be introduced without redesigning SentinelCrypt's architecture. They reduce trust in the live application for offline evidence review and reduce key exposure to data-processing components. They do not make a fully compromised host trustworthy.

## 7. Explicit exclusions and residual risks

SentinelCrypt does not currently provide a distributed immutable ledger, blockchain consensus, hardware-backed key custody, external trusted timestamping, general API authentication/RBAC, or an independent source of truth for all database/filesystem state. SHA-256 and a local hash chain provide integrity checks over supplied data, not distributed immutability. Ed25519 signatures authenticate bytes relative to a key, not scientific claims or signer identity without an external trust anchor.

An attacker who controls the host, administrator account, application process, database and artifact directories, signing key, or build/release path may be able to replace outputs and the metadata used to check them. The strongest practical response is to move verification and preservation anchors outside that control domain, not to add more self-checks within the same one.

## 8. Review and validation

Reassess this TCB when any of these change: API authentication/authorization; deployment topology; database or filesystem backend; serialized artifact format; evidence package or cryptographic protocol; notary key custody; verifier implementation/dependencies; experiment runner; or CI/release process.

This is architecture documentation only. It introduces no runtime security control, and therefore requires no new automated test. Deployment controls in Section 6 should be validated operationally for the specific environment; repository unit tests cannot prove external key custody, separate-host preservation, or OS access policy.
