# Independent SentinelCrypt Evidence Verifier

`sentinel-verify <evidence-package>` checks an exported evidence directory
offline. The verifier is implemented in `scripts/sentinel_verify.py` and does
not import React, FastAPI, SentinelCrypt application services, the database,
the ML training stack, or any network client. Its base operation uses Python's
standard library. Ed25519 verification imports the `cryptography` package only
when a notary artifact is present; the verifier fails closed if that dependency
is unavailable. The evidence package contains the verification inputs and
declared artifacts; it does not bundle the verifier or Python runtime.

## Install and run

From a repository checkout:

```console
python scripts/sentinel_verify.py results/evidence/EXP-A
python scripts/sentinel_verify.py results/reproducibility/EXP-A --json
```

After installing the project:

```console
sentinel-verify path/to/evidence-package
sentinel-verify path/to/evidence-package --json
```

No application server, SentinelCrypt database, model artifact, dataset, or
internet connection is required. Evidence packages are directories; archives
must be safely extracted before verification. The verifier does not extract
archives itself.

## Offline inputs and dependencies

The two exported directory layouts carry their verification data:

| Package layout | Included verification inputs |
|---|---|
| Direct evidence | `package-manifest.json`, `verification-report.json`, `experiment.json`, `metrics.json`, `reproducibility-manifest.json`, `README.md`, and `file-hashes.json` |
| Reproducibility | `package-manifest.json`, `verification-report.json`, `results.json`, its matching `evidence/experiment.json`, `metrics.csv`, `model-metadata.json`, `dataset-manifest.json`, `environment.json`, configuration/instructions, and `file-hashes.json` |

These are exported metadata and evidence artifacts, not the original dataset or
trained model weights. The verifier reads only the package and its own code: it
does not fetch data, load a model, connect to a database/API, start a frontend,
or invoke training. An offline host needs a compatible Python interpreter.
Unsigned packages can be checked with Python's standard library alone. When a
package includes a notary signature, the offline host must also have the
`cryptography` package installed to verify Ed25519; the package embeds the
signature and public key, but does not embed this third-party implementation.
Provision that dependency before disconnecting if signed-package verification
is required. No network is used during verification.

## Status and exit codes

| Status | Exit | Meaning |
|---|---:|---|
| `VERIFIED` | 0 | The supported package structure was present and all performed integrity and consistency checks passed. Optional absent audit/notary artifacts are reported as warnings. |
| `FAILED` | 1 | Package integrity, a required check, signature, lineage, or consistency check failed. |
| `INVALID_FORMAT` | 2 | The input is not a supported evidence package, is incomplete, or contains malformed required files/schemas. |
| `UNSUPPORTED_VERSION` | 3 | A declared package, protocol, schema, experiment, or research-artifact version is not supported. |

For automation, `--json` emits an object with `status`, `verified`, `exit_code`,
per-check results, and supported version lists. The process exit code is the
authoritative success/failure signal.

## Verification performed

The verifier checks the package-manifest version declarations and their
consistency with the verification report; minimum required files for the
direct-evidence and reproducibility package layouts; basic JSON object schemas;
SHA-256 file inventory entries and artifact presence; experiment/result hash
recomputation; duplicated evidence/result and metrics consistency; experiment
and dataset lineage fields when included; exported audit-chain structure,
sequence continuity, payload digests, and previous-hash linkage; and Ed25519
signatures over the canonicalized notary payload when included. Duplicate keys
in JSON objects are rejected to avoid parser-dependent interpretations of
security-sensitive fields.

Format-2 direct evidence packages include `file-hashes.json` with hashes for
the other package files. `file-hashes.json` is intentionally not self-hashed.
The reproducibility export also maintains that layout; its package hash is
computed over the canonical file inventory. The verifier rejects inventory
paths that are absolute, traverse outside the package, contain Windows-style
path separators, or resolve through a symlink outside the package.

## Trust and limitations

Successful verification means the checks described above pass against the
package's own declarations. A SHA-256 inventory is not independently
authenticated unless its expected digest is trusted through a separate
channel. An Ed25519 signature made with a key embedded in the same artifact
proves that the artifact matches that key, but does not establish the key
owner's identity or trustworthiness. `signed_at` and other embedded timestamps
are not trusted time. The verifier cannot prove that a dataset was honest, a
model was trained as claimed, an experiment was scientifically valid, or
records were never removed before package creation. A valid hash chain is not
distributed immutability or a blockchain.

The verifier rejects a package when its signature cannot be checked; missing
`cryptography` is not treated as successful verification. This dependency is
already part of SentinelCrypt's project dependencies. Audit ledgers and notary
signatures are optional if the exported layout does not include them; their
absence is reported as a warning, not proof that those protections were used.

### What can be independently verified offline

Given a supported package and verifier, the CLI can check version declarations,
required file presence and basic schemas; compare package-internal experiment,
report, metrics, and lineage fields; recompute declared result and SHA-256 file
hashes; validate an included audit chain's sequence and links; and validate an
included Ed25519 signature if `cryptography` is installed. These are checks of
the bytes and claims supplied in the package. They require no live SentinelCrypt
service, database, frontend, dataset, or model runtime.

### What cannot be independently verified offline

The package does not contain the source dataset or trained model weights. A
dataset hash in a manifest is only a recorded claim without the corresponding
dataset bytes; likewise, model metadata does not establish how the model was
trained or whether it produced the reported output. The verifier cannot rerun
training, preprocessing, inference, or metric calculations, validate external
dependency behavior, or establish scientific correctness/reproducibility from
metadata alone. Doing so may require the original data, model/runtime,
environment, external packages, or other inputs described in the reproduction
instructions. Offline integrity verification is not full scientific
reproducibility.

A passing `VERIFIED` status means only that the performed package-local checks
passed. It does not authenticate the file inventory unless its expected digest
is trusted independently, establish signer identity when the key is supplied
inside the package, or prove that evidence was not omitted before export.

## Compatibility

The verifier accepts legacy evidence format 1 according to the compatibility
rules in [PROTOCOL_VERSIONING.md](./PROTOCOL_VERSIONING.md), and current
format 2. Unknown explicit protocol/schema versions fail with
`UNSUPPORTED_VERSION`; an explicit malformed or incomplete manifest is not
silently treated as legacy. Format-2 directory exports require a package
manifest, verification report, and file inventory.

## Tests

```console
pytest backend/tests/unit/test_sentinel_verify_cli.py backend/tests/unit/test_protocol_versioning.py -q
```

The CLI tests cover direct-package verification, hashes, evidence/lineage
consistency, traversal rejection, malformed and incomplete packages,
unsupported versions, duplicate/reordered/deleted ledger records, offline
signature verification, JSON status/exit behavior, and execution as a separate
Python process.
