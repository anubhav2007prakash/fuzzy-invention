# Cryptographic Research Artifact Lineage

## Scope

SentinelCrypt persists lineage records for artifacts that its application actually creates. The graph records the artifact ID and type, parent artifact ID, UTC creation time, format version, SHA-256 digest, optional Git commit and experiment ID, and JSON metadata.

The primary training path is:

`Raw Dataset → Validated Dataset → Processed Dataset → Training Configuration → Model → Results → Report`

When inference and explainability are used, additional derived artifacts are recorded:

`Model → Prediction → Explanation → Experiment Analysis → Results → Report`

Audit evidence is a separate child of its prediction. Experiment evidence-package exports add experiment, results, verification-report, and evidence-package nodes. These are connected to the nearest actual parent available; the service does not manufacture missing earlier stages.

## Digest semantics

- Raw dataset: SHA-256 of the bytes stored by the dataset ingestion service.
- Validated dataset: SHA-256 of the canonical validation status and summary fields.
- Processed dataset: SHA-256 of canonical metadata containing the feature names, shapes, and SHA-256 digests of the train/test arrays and labels.
- Training configuration: SHA-256 of canonical configuration and feature schema metadata.
- Model: SHA-256 of metadata containing SHA-256 digests of the serialized model and preprocessing artifacts.
- Prediction: SHA-256 of canonical prediction evidence.
- Explanation: SHA-256 of canonical explanation fields.
- Audit evidence: the existing hash-chain record hash.
- Experiment results/report: SHA-256 of canonical result/report payloads. Exported instances include a digest prefix in their artifact IDs, so a later export with different results or timestamps creates a new immutable lineage node rather than overwriting history.
- Evidence package: package hash computed over the package's declared file inventory.

These records bind declared digests to lineage metadata. The graph endpoint verifies graph structure and SHA-256 syntax, not the continued presence or contents of every external file. File/artifact verification remains the responsibility of the relevant evidence verifier.

## Persistence, integrity, and compatibility

The `artifact_lineage` table is introduced by Alembic revision `0003_lineage`. Installations using Alembic should apply migrations with `alembic upgrade head`. `Base.metadata.create_all` also registers the model for fresh test and development databases; it does not upgrade an existing database schema.

Parents must already exist or appear earlier in the same `record_chain` request. IDs are immutable: recording an existing ID is idempotent only when its lineage fields and metadata match exactly; when creation time is omitted on retry, the stored original time is retained. Conflicts, missing parents, invalid digests, malformed metadata, or cycles are errors. Database foreign keys restrict deletion of a lineage parent. Historical lineage is not automatically deleted when an application-level model or dataset is removed.

Legacy records are not silently backfilled. A prediction made with a legacy model that has no lineage record is explicitly recorded as a root with a metadata warning instead of claiming a nonexistent parent.

The API is `GET /api/v1/research/lineage`. Its `integrity` value of `structurally_valid` means parent links exist, the graph is acyclic, metadata parses, and digest strings have SHA-256 syntax. It does not mean the database is tamper-proof, that file hashes were recomputed, or that the evidence is externally authenticated.

## Limits

Lineage is a database-backed provenance record. SHA-256 provides content-digest comparison, not identity authentication or distributed immutability. A privileged database or host attacker can alter both records and digests. A missing artifact is not reconstructed from a digest. Git commit values are recorded only when available from the runtime environment; they are not asserted otherwise.

Deterministic validation should cover parent existence, append/idempotency conflicts, digest formatting, cycle detection, graph response shape, data-to-model lineage, and explicit integrity errors for dangling records.
