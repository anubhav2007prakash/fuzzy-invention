# SentinelCrypt protocol and artifact versioning

This document defines the independent version identifiers used by exported
SentinelCrypt evidence. The identifiers are compatibility declarations; they
do not add authentication to unsigned files, and a version number alone is not
evidence that a package came from a particular SentinelCrypt deployment.

## Current and supported versions

| Identifier | Current export | Supported by current verifier | Meaning |
|---|---:|---|---|
| `evidence_format_version` | 2 | 1 and 2 | Directory/package layout. Format 2 adds `package-manifest.json`; format 1 is the legacy layout without that file. |
| `protocol_version` | 1 | 1 | Cryptographic rules: deterministic canonical JSON, SHA-256 payload/record hashing and the forward-linked ledger, plus the existing Ed25519 research notary. |
| `schema_version` | 1 | 1 | Schema of version metadata and the package verification envelope. |
| `experiment_schema_version` | 1 | 1 | Shape and interpretation of the experiment result/run-manifest data. |
| `research_artifact_version` | 1 | 1 | Shape of the notary research artifact (`sentinelcrypt.research-artifact.v1`). |

New evidence package exports include `protocol_version` and `schema_version`
in both `package-manifest.json` and `verification-report.json`. They also
declare the package format, experiment schema, and research artifact versions.
The experiment run manifest declares `experiment_schema_version`. The
`export_evidence_package` and `export_reproducibility_package` API results
include the version metadata as well. Newly signed notary artifacts declare
`protocol_version`, `schema_version`, and `research_artifact_version`.

The `package-manifest.json` is included in the reproducibility package's file
hash inventory. The ordinary experiment evidence export's package hash covers
all exported files, including its version manifest. These hashes provide
integrity checking only relative to a trusted expected hash; without an
independently retained checkpoint or signature, they do not make the package
immutable or authenticate the version manifest.

## Backward compatibility and migration

* A package with no `package-manifest.json` is treated as evidence format 1.
  Missing legacy protocol/schema/component version fields are interpreted as
  version 1. This preserves verification of existing valid packages.
* A format-2 package must have a JSON-object `package-manifest.json` with every
  version field listed above. Missing, malformed, or unsupported explicit
  values fail verification; an explicit manifest is not silently treated as
  a legacy package.
* Verification-report and notary envelope fields omitted by legacy v1
  artifacts use v1 compatibility rules. Explicit unknown values and unknown
  research-artifact types are rejected rather than verified using v1 rules.
* Version 1 protocol and schemas are the only supported cryptographic,
  experiment, and research-artifact versions today. Evidence format 1 is
  supported for reading only; new package exports use format 2.
* A future incompatible change must define the new version's serialization,
  digest/signature coverage, schema, and verifier behavior before it is
  emitted. Keep old verification behavior available for previously supported
  versions. Never reinterpret old bytes or silently rewrite a signed payload.
* To migrate an old package, preserve it unchanged as the historical record.
  Re-export from the original experiment/result when a format-2 package is
  needed. The re-export is a new package with a new manifest and package
  hashes; it is not a byte-preserving conversion and does not retroactively
  authenticate the source package.

## Signature and version-field scope

Protocol v1 research signatures cover the SHA-256 digest of the canonical
`payload` only. The envelope's version fields, `signed_at`, `artifact_type`,
key fingerprint, and other metadata are not included in that signed digest.
The verifier requires any explicit version/type to be supported, but accepts
missing v1 fields for legacy artifacts. Therefore version metadata is useful
for format selection and compatibility, not authenticated by a v1 signature.
Do not use `signed_at` as trusted time or infer an externally anchored notary
identity from an embedded public key alone.

The hash-chain formula and canonicalization protocol have not changed here, so
their protocol remains v1. Adding a package manifest is an evidence format
change, not a change to existing evidence payload digests or signatures.

## Compatibility tests

`backend/tests/unit/test_protocol_versioning.py` checks supported current and
legacy package versions and rejection of unknown or incomplete explicit
manifests. `backend/tests/unit/test_notary.py` checks versioned v1 artifacts,
legacy artifacts with absent version fields, and rejection of unsupported
protocol, schema, or artifact versions. Export tests assert both API metadata
and on-disk manifests.
