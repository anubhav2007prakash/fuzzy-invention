# SentinelCrypt AI — Cryptographic Design Specification

## Purpose
Provide tamper-evident integrity checking for stored prediction evidence.

## Primitive
SHA-256 from a standard maintained cryptographic implementation.

## Canonicalization
Use UTF-8, deterministic JSON, sorted keys, explicit field names, stable timestamps, and normalized integrity-critical values.

## Record
```json
{
  "record_id": "...",
  "timestamp": "...",
  "previous_hash": "...",
  "payload": {},
  "record_hash": "..."
}
```

## Digest
`record_hash = SHA256(previous_hash || canonical_payload)`

The exact byte encoding must be documented and tested.

## Verification
Recreate canonical payload → recompute digest → compare stored digest → confirm previous-link → report first failure.

## Properties
Detects specified modifications under the trust assumptions. It does not provide distributed consensus, guaranteed immutability, host compromise resistance, secrecy, or authenticity of an ML prediction.

## Required Tests
Unchanged chain; payload mutation; previous-hash mutation; deletion; insertion; reordering; malformed canonical data.
