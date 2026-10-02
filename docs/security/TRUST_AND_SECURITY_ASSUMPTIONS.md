# SentinelCrypt Trust and Security Assumptions

**Status:** Repository-grounded trust model  
**Scope:** SentinelCrypt AI application and its evidence/research workflows  
**Audience:** Operators, developers, researchers, and consumers of exported evidence  
**Assessment basis:** Current repository implementation and tests; this document does not assert controls that are merely recommended or planned.

## 1. Purpose and security posture

SentinelCrypt is a research prototype composed of a FastAPI backend, React/Vite frontend, SQLAlchemy database layer (SQLite by default), local data/model/result files, ML and XAI code, and cryptographic evidence utilities. Its controls can validate inputs, prevent some unsafe file paths, detect certain inconsistencies, and make some post-hoc edits evident when the verifier is given the complete unmodified evidence.

SentinelCrypt is **not** a production security product, an identity provider, a secure multi-tenant service, a hardware-backed key service, a trusted timestamp authority, a remote append-only ledger, or a blockchain. Its cryptographic checks do not make the host, database, filesystem, administrator, input data, dependencies, or exported claims trustworthy.

## 2. Trusted components and minimum trusted computing base

### Components trusted for a local, authorized research deployment

These are trust assumptions, not independent guarantees:

- The OS instance, Python runtime, process environment, and host account that run the backend.
- The backend code and configuration actually deployed, including route handlers, validators, canonicalizer, hash-chain verifier, and notary implementation.
- The cryptographic implementation supplied by the installed `cryptography` package and its runtime dependencies.
- The configured database and filesystem, including their access controls, backup/restore process, and integrity at the time of verification.
- The notary private key and the operator's trusted distribution/pinning of its public-key fingerprint, if signer identity is being asserted.
- The dataset/model/experiment artifacts that an operator has explicitly reviewed and chosen to trust.
- The CI/build/release chain that produced the deployed code and dependency environment.

### Minimum trusted computing base (TCB)

For the narrow claim **“these supplied ledger records are internally consistent under the implemented SHA-256 chain rules”**, the minimum TCB is:

1. The verifier and canonicalization/hash implementations being run.
2. A functioning Python runtime and SHA-256 implementation.
3. The complete ordered set of records supplied to the verifier, including trustworthy provenance for that set if completeness matters.

For the stronger claim **“this research artifact was signed by the SentinelCrypt operator”**, the TCB additionally includes:

1. The trusted Ed25519 verification implementation.
2. The genuine public key/fingerprint obtained through a trusted, independent channel.
3. The signing host/process and its private key at the time of signing.
4. The signed payload and the trustworthiness of the process/data that produced it.

The application, database, filesystem, frontend, ML/XAI stack, operator host, and release supply chain join the TCB for claims about how data was collected, which model produced a result, or whether an export is complete and current. No current feature removes those dependencies.

## 3. Untrusted components and inputs

Treat these as untrusted until validated or independently authenticated:

- Browser clients, frontend code, browser storage, and every client-supplied request parameter/body/header.
- Uploaded filenames and CSV bytes, including syntactically valid files with adversarial values, extreme dimensions, misleading labels, or poisoned examples.
- Imported/exported JSON, notebooks, reports, model files, preprocessing files, and other artifacts received from outside the trusted deployment.
- Database rows and filesystem contents when an attacker, administrator, restore operation, or other process could have changed them.
- Experiment names/configuration/metadata and timestamps supplied or derived from a caller-controlled or mutable source.
- A public key included only inside the same signed artifact when deciding who signed it. It is sufficient to check internal signature consistency, not signer identity.
- Network services, package registries, dependencies, CI actions, container images, build tools, and release artifacts unless pinned, verified, and controlled by deployment policy.
- Timestamps from the host clock, database, file metadata, or self-reported artifact fields absent an independently trusted time source.

API schema validation and upload checks reduce malformed-input risk; they do not make data truthful, benign, authorized, or safe for resource-intensive processing. Some endpoints accept flexible dictionary-shaped research inputs, so consumers must not assume uniform strict schemas across the whole API.

## 4. Trust boundaries

| Boundary | What crosses it | Current trust rule |
|---|---|---|
| Browser/client ↔ API | HTTP requests, uploaded files, IDs, configuration, responses | Client input is untrusted; frontend checks are not authorization. Backend validation is the relevant input control. |
| API ↔ DB | Dataset/model/experiment/prediction/audit metadata | ORM/SQL constraints protect ordinary writes; direct DB access or host compromise can alter data and the verifier's inputs. |
| API ↔ filesystem | Raw/processed data, models, preprocessing objects, results, keys | Server-generated upload names and path checks mitigate some path abuse; local ownership, permissions, symlink behavior, and concurrent changes remain OS/deployment responsibilities. |
| ML/XAI process ↔ data/artifacts | CSV parsing, model execution, SHAP inputs, joblib/pickle files | Data and serialized artifacts can be adversarial. `joblib`/`pickle` deserialization can execute code; only load artifacts from a trusted source in a suitably isolated process. |
| Backend ↔ notary key | Signing and verification operations | The local unencrypted key is a demo trust root. Anyone able to replace/read it or control the signing process can undermine the signer claim. |
| Build/release ↔ external supply chain | Python/npm packages, GitHub Actions, images, toolchain | Installed code is trusted only to the extent the dependency and build chain is trusted. Current Python requirements use lower-bound version ranges; CI/security workflow files contain checkout steps only. |
| Application ↔ operator/admin | Configuration, mode, DB, files, keys, deployment | A privileged operator/host user can generally modify all local state. No cryptographic control can make that actor untrusted while relying solely on the same host. |
| Export ↔ recipient | Evidence package, signature, public key, timestamp, reports | Exported content can be copied, truncated, replayed, or modified. Recipient must pin signer identity and obtain freshness/completeness evidence externally when those claims matter. |

## 5. Security assumptions by concern

### Cryptography and ledger

- SHA-256 is assumed to be collision/second-preimage resistant for the application's use; Ed25519 is assumed to provide signature unforgeability when used correctly with a secret key. These are algorithm/library assumptions, not a proof of deployment correctness.
- Audit payload JSON is canonicalized before hashing. A record hash is computed as `SHA-256(previous_hash || payload_hash)`, starting at a fixed all-zero genesis value.
- The hash chain is a local tamper-evidence mechanism. It is **not distributed immutability**, consensus, replication, blockchain, or protection against a party that can rewrite the complete chain and all verification inputs.
- Verification sorts records by sequence number and checks links, continuity, payload hashes, and record hashes. Reordering rows alone is normalized; missing interior records or duplicate/gapped sequences are detectable. A valid prefix can still verify after its tail is removed: the verifier has no external expected-tip or record-count anchor.
- A valid signature over a supplied public key proves only that the matching private key signed the digest. If the key is accepted solely because it is bundled in the artifact, the artifact can be self-consistently signed by an attacker's key. A trusted, out-of-band fingerprint is necessary to identify the operator.
- The artifact's `payload_hash` and signature cover canonical payload bytes. Envelope metadata such as `signed_at` and `key_fingerprint` is not itself part of the signed payload in the current implementation; do not use it as authenticated time or identity evidence without independent checks.
- `/notary/sign` rejects arbitrary caller-selected claims. `/notary/sign-experiment` signs the experiment result retrieved by the server, but the result's provenance and the signing process remain within the trust base.

### Database

- The database is assumed available, correctly initialized/migrated, and writable only by authorized application/operations processes.
- SQLite is the default. SQLAlchemy constraints and database integrity audits detect selected ordinary relational errors (such as sequence gaps, duplicate audit sequences, orphan references, and impossible timestamp orderings); they do not prevent a privileged direct writer from changing rows or rebuilding consistent records.
- Database transactions do not atomically include every filesystem artifact operation. Files and database metadata can diverge on failures, concurrent changes, restore, or manual edits.
- A database backup is not automatically an independently trusted ledger checkpoint. No current service provides a remote witness of the ledger tip.

### Filesystem and operating system

- Upload validation limits accepted filenames/extensions and upload size; uploaded files are assigned UUID-based storage names and checked for directory containment.
- These measures assume the configured directories and their parent paths are controlled by the service operator. They do not guarantee protection against a compromised process/host, hostile directory permissions, races between path verification and use, or modification of files by another privileged process.
- The original upload name is metadata, not a trusted storage path.
- Serialized model/preprocessing artifacts are executable inputs. Filesystem location alone is not proof of integrity or safety.
- The OS, service account, process isolation, secrets/environment, clock, and file permissions are trusted. The notary code attempts mode `0600` for the private key where supported; on Windows it treats this as best effort. Key bytes are written without encryption.

### Dependencies and build

- Runtime behavior and security depend on Python, Node/browser tooling, all installed packages, system libraries, CI actions, and deployment images.
- The Python requirements specify minimum versions rather than a fully hash-locked runtime environment. A dependency declaration is not evidence that the installed version is safe, reproducible, or uncompromised.
- The checked-in CI/security workflows currently contain only checkout steps; they do not establish that tests, static analysis, dependency audits, artifact signing, or provenance checks ran.
- Production claims therefore require an independently controlled build pipeline, reviewed/pinned dependencies and actions, vulnerability response, and release provenance; these controls must not be inferred from the presence of workflow files.

### Timestamps and key management

- Timestamps are generated/read from local system clocks or stored records. Clock skew, manual changes, time-zone mistakes, replay, and metadata alteration are possible.
- The DB temporal audit checks selected causal relationships with a configured skew tolerance; it cannot establish absolute UTC correctness or prove when an event occurred.
- Notary `signed_at` is a process-generated UTC string, not a trusted timestamp token. It is not currently bound into the signature over the payload.
- The notary keypair is generated locally under `results/notary/` with no passphrase/encryption or remote KMS/HSM. Backups, rotation, revocation, access review, and external fingerprint distribution are operator responsibilities and are not implemented as a full production key lifecycle.

### Administrators and identity

- The repository-visible API does not establish a general authenticated principal/RBAC/object-authorization boundary. CORS is not authentication, and Demo Mode is an operational read-only guard, not an authorization boundary.
- Mode is module-level runtime state and the mode endpoint is an escape hatch. A remote caller able to reach exposed routes must not be assumed to be blocked by frontend controls or Demo Mode alone.
- Administrators and anyone controlling the host, process, DB, filesystem, configuration, or signing key are trusted for local operation. If such an actor is malicious or compromised, integrity and confidentiality claims are limited to externally anchored evidence produced before compromise.
- Treat public/network exposure as unsafe unless external authentication, authorization, network restrictions, and operational controls are added and verified.

## 6. What SentinelCrypt protects against

Subject to the assumptions above, the implementation can:

- Reject a set of malformed requests with client errors instead of accepting them or producing server errors.
- Reject unsafe upload filenames, non-CSV extensions, and some traversal/absolute-path forms; store accepted uploads under server-generated names and check their resolved containment.
- Detect many accidental or partial edits to supplied audit records, including payload changes, broken hash pointers, sequence gaps, and duplicate sequence numbers.
- Detect selected relational inconsistencies using the database integrity audit.
- Detect payload changes or invalid signatures in a signed artifact when the digest and signature are checked.
- Distinguish the current local notary public key from a different self-consistent public key via its fingerprint comparison, provided the verifier's local trust anchor is itself trusted.
- Prevent the legacy arbitrary-payload signing route from certifying caller-selected claims.

These are bounded properties of code paths and test cases; they do not imply complete API safety or comprehensive malicious-input defense.

## 7. What SentinelCrypt does not protect against

SentinelCrypt does not currently guarantee:

- Authentication, authorization, tenant isolation, or prevention of unauthorized API reads/writes.
- Truthfulness, provenance, representativeness, cleanliness, or non-poisoning of an uploaded dataset.
- Safe execution of untrusted serialized models or preprocessing artifacts.
- Prevention of database/filesystem tampering by a privileged user, compromised service, malware, or host administrator.
- Detection of every possible record deletion: in particular, deletion of a valid chain tail can leave a valid prefix unless an external expected tip/length is checked.
- Protection against a complete ledger rewrite when no independently retained checkpoint exists.
- Distributed or blockchain immutability, consensus, independent witnessing, or non-repudiation beyond a signature under a trusted key.
- Proof that the public key in an artifact belongs to SentinelCrypt, unless its fingerprint is authenticated independently.
- Trusted wall-clock time, event ordering against a hostile clock, or authenticated timestamping.
- Confidentiality at rest, encrypted signing-key storage, production-grade key custody, recovery, rotation, or revocation.
- Guaranteed atomic consistency between DB rows and filesystem artifacts.
- Reproducible or safe builds, vulnerability-free dependencies, or trustworthy CI status from the current workflow definitions.
- Availability under denial of service, resource exhaustion, storage exhaustion, or expensive ML/XAI workloads.
- Protection after compromise of the trusted runtime, cryptographic library, administrator, OS, or signing process.

## 8. Mechanically validated assumptions

Existing tests exercise filename validation/storage containment (`backend/tests/unit/test_file_security.py`), production secret/configuration constraints (`backend/tests/unit/test_config.py`), ledger hashing and tamper detection (`backend/tests/unit/test_hashing.py`, `backend/tests/unit/test_security_redteam.py`), notary verification and foreign-key identity distinction (`backend/tests/unit/test_notary.py`), and selected relational/timestamp invariants (`backend/tests/unit/test_db_integrity.py`).

The explicit boundary tests in `backend/tests/unit/test_security_redteam.py` verify that deleting only the tail yields a valid prefix absent an external checkpoint, and `backend/tests/unit/test_notary.py` verifies that modifying unsigned envelope time metadata does not authenticate that time or invalidate a payload signature. These tests document current limits; they are not endorsements of those limits.

Controls that depend on real deployment state—permissions, key custody, package provenance, trusted clocks, external ledger checkpoints, or administrator identity—cannot be proven by these unit tests and require deployment/operational verification.

## 9. Minimum deployment conditions for relying on evidence

Before relying on evidence for a consequential decision:

1. Run the verifier over the complete expected record range and compare its final sequence/hash against a checkpoint retained outside the application host.
2. Obtain and pin the notary public-key fingerprint through a trusted channel independent of the artifact being checked.
3. Confirm the artifact/model/dataset provenance and integrity independently; do not deserialize an untrusted model or preprocessing object.
4. Restrict API reachability and host/DB/filesystem access; do not treat CORS, UI controls, or Demo Mode as access control.
5. Record the exact application build, dependency set, data/model hashes, configuration, and trusted clock source used for the run.
6. Treat timestamps as descriptive unless authenticated by a trusted timestamping service.
7. Preserve backups/checkpoints outside the administrative control plane of the SentinelCrypt host.

Reassess these assumptions when authentication, remote deployment, multi-user operation, key lifecycle, artifact formats, persistence, or signing protocol changes.
