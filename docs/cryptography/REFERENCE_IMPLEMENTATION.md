# SentinelCrypt Cryptographic Reference Implementation

The package at `backend/app/cryptography/reference/` is a readable,
test-oriented implementation of the cryptographic protocol used by
SentinelCrypt. It prioritizes direct, inspectable steps over performance and
is not imported by the production application. Differential tests compare it
with production code.

The reference uses only standard JSON/UTF-8 handling, Python `hashlib`
SHA-256, and Ed25519 from `cryptography`. It does not define a custom
cryptographic primitive. It is not itself an external audit, identity trust
service, or protection against a compromised host.

## Protocol components

| Component | Production implementation | Reference implementation |
|---|---|---|
| Canonical JSON text | `backend/app/cryptography/canonicalization.py` | `reference/canonical.py` |
| SHA-256 digest | `backend/app/cryptography/hashing.py` | `reference/digest.py` |
| Payload and record hashes | `backend/app/cryptography/hash_chain.py` | `reference/chain.py` |
| Ledger verification | `backend/app/cryptography/verifier.py` | `reference/chain.py`, `reference/verify.py` |
| Signed research artifacts | `backend/app/cryptography/notary.py` | `reference/signature.py` |
| Merkle root and proofs | `backend/app/cryptography/merkle.py` | `reference/merkle.py` |

## Canonical representation and encoding

For the protocol's JSON-compatible payloads, canonicalization produces a
compact JSON string with recursively sorted string keys, no optional
whitespace, and non-ASCII characters preserved. The string is encoded as
UTF-8 before it is hashed.

The production serializer uses Python's `json.dumps` with
`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, and
`allow_nan=False`. Its datetime extension serializes a naive datetime as UTC
and calls `isoformat()`; timezone offsets on aware datetimes are preserved.
Python's JSON encoder supplies float formatting. NaN and infinities are
rejected. Unsupported values such as `Decimal` and raw `bytes` are not silently
converted.

This protocol convention is **not RFC 8785 / JSON Canonicalization Scheme
(JCS)**. Do not treat its output as interoperable JCS data. Object keys in
protocol payloads are strings; the reference rejects non-string keys rather
than silently coercing them and creating possible key collisions.

```python
from backend.app.cryptography.reference.canonical import canonicalize

text = canonicalize({"z": 2, "a": {"label": "café"}})
assert text == '{"a":{"label":"café"},"z":2}'
encoded = text.encode("utf-8")
```

## SHA-256 digest and hash chain

For a payload `P`:

```text
canonical_bytes = UTF8(canonicalize(P))
payload_hash    = lowercase_hex(SHA-256(canonical_bytes))
record_hash     = lowercase_hex(SHA-256(UTF8(previous_hash + payload_hash)))
```

`previous_hash` and `payload_hash` in the record formula are their lowercase
hex strings, concatenated as UTF-8 text with no delimiter. The first previous
hash is 64 ASCII zeroes (`GENESIS`). Each following record points to the
previous record's `record_hash`.

`build_chain(payloads)` returns records in input order with a sequence number,
canonical `payload_json`, previous hash, payload hash, record hash, and a
creation timestamp. Timestamps are generated at construction and are not
trusted time; they do not make the deterministic hash calculation
deterministic across separate builds.

`verify_chain(records)` sorts records by sequence number and recomputes
sequence continuity, previous-hash linkage, payload hash, and record hash.
The reference returns a boolean and descriptive errors. Ledger verification
also has a plain-dictionary adapter that mirrors the production verifier's
verification result.

## Ed25519 signed research artifacts

The notary signs the 32-byte SHA-256 digest of the canonical UTF-8 payload
using Ed25519 from the `cryptography` package. Verification recomputes the
digest and verifies the signature against the artifact's embedded raw public
key. The reference can verify artifacts made by the production notary and
can create artifacts accepted by the production verifier.

`sign_result(payload)` generates a fresh in-memory research key by default;
callers may supply a key explicitly. It does not load or use the production
notary key. The reference artifact includes the currently supported
`protocol_version`, `schema_version`, and `research_artifact_version` values.
The artifact's embedded public key makes mathematical verification possible,
but by itself does not establish signer identity or key custody.

Key export helpers, if used for examples, write unencrypted private PEM
material. Do not use them as a production key-management design.

## Merkle tree

Merkle leaves and internal nodes use domain-separated SHA-256:

```text
leaf_hash(payload) = SHA-256(0x01 || UTF8(canonicalize(payload)))
node_hash(left, right) = SHA-256(0x00 || left_digest_bytes || right_digest_bytes)
```

Tree roots and proof siblings are lowercase hex. An unpaired node at a level
is duplicated. The production tree returns digest bytes from `leaf_hash()`;
the reference uses lowercase hex strings for inspection. Their roots and proof
paths must be identical for the same payloads. For a proof, production takes
the already-hashed leaf bytes; reference membership verification takes the
canonical payload bytes and hashes the leaf as its first step.

The tree constructor treats byte-valued leaves as already-hashed leaf bytes,
matching production. For normal JSON payloads, it computes the domain-separated
leaf digest itself.

## Differential verification

Run the focused component comparisons from the repository root:

```powershell
python -m pytest backend/tests/differential/test_canonicalization_differential.py `
  backend/tests/differential/test_hashing_differential.py `
  backend/tests/differential/test_hash_chain_differential.py `
  backend/tests/differential/test_reference_signature.py `
  backend/tests/differential/test_reference_merkle.py `
  backend/tests/differential/test_reference_verification.py -q
```

The comparison tests cover canonical output and UTF-8 behavior, SHA-256 known
answers, payload/record hashes, ledger verification outcomes, signatures
verified in both production-to-reference and reference-to-production
directions, and Merkle roots, paths, and membership results over even and odd
tree sizes. Generated differential tests provide additional reproducible
input coverage. Assertion diagnostics identify the component, payload or
case, and both outputs.

The production and reference implementations share standard underlying
libraries for SHA-256 and Ed25519, but they do not share SentinelCrypt helper
functions. The tests are comparisons, not a claim of formal verification.

## Limits and interpretation

- SHA-256 and a local hash chain can detect changes relative to known expected
  values. Without an independently trusted checkpoint, they do not establish
  record truth, completeness, or resistance to privileged rewriting and
  deletion.
- A signature verified against an embedded key proves only that the matching
  private key signed the digest. Identity binding, secure custody, rotation,
  and revocation require external trust and key-management controls.
- A Merkle proof establishes inclusion relative to the supplied root, not
  whether that root is authentic or complete.
- Timestamps are metadata, not an external timestamp authority.
- Cryptographic verification does not prove scientific validity,
  reproducibility, dataset provenance, or model correctness.

