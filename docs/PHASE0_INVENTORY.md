# Phase 0 — Implementation Inventory (read before modifying)

Date: 2026-09-24 · Purpose: what already exists, so the Devil's-Advocate phases **extend** rather than duplicate.

## Existing capability map

| Area | Implementation | Tests |
|---|---|---|
| Canonical JSON | `backend/app/cryptography/canonicalization.py` — `json.dumps(sort_keys, separators, default=...)`; floats rounded to 6dp; datetime → ISO | `test_hashing.py` |
| SHA-256 hashing | `hashing.py` — `sha256_hash` (str/bytes), `hash_file` (chunked) | `test_hashing.py` |
| Hash chain | `hash_chain.py` — `record_hash = SHA256(prev + payload_hash)`; genesis = 64×"0" | `test_hashing.py`, `test_verifier.py` |
| Verifier | `verifier.py::verify_ledger` — sequence continuity, prev-hash linkage, payload re-canonicalization, record-hash recompute | `test_verifier.py` |
| Merkle tree | `merkle.py` — inclusion proofs, tamper detection (EXP-G) | `test_new_experiments.py` |
| Ed25519 notary | `notary.py` — sign/verify canonical digests, demo keypair under `results/notary/` | research suite |
| Reproducibility | `research/reproducibility.py` — env manifest, manifest diff, 10-file package export (package hash = pure fn of result) | `test_research_api.py` |
| Falsification | `research/falsification.py` — EXP-FALSIFICATION, criteria-gated verdicts (5 claims) | `test_falsification.py` |
| Metamorphic | `research/metamorphic.py` — 3 relations + metamorphic hash-oracle | `test_metamorphic.py` |
| Challenge framework | `research/challenges.py` — Q1–Q5 presets, persisted JSON runs | research suite |
| Benchmark suite | `research/benchmark.py` — UNSW-NB15/CICIDS2017 **synthetic proxies (labelled)**, 11 metric families, JSON+MD report | `test_benchmark.py` |
| Pipeline overhead | `research/overhead.py` — 5-ladder baseline (ML → +XAI → +crypto → full), repeated runs | `test_overhead.py` |
| App modes | `research/modes.py` — research/demo; demo default-denies non-golden-path POSTs | `test_modes.py` |
| Frontend | React 18 + Vite; 33 vitest tests (dead-field regressions, QuickFind, charts) | `npx vitest run` |
| Backend suite | 402 passed / 1 skipped (pytest) | — |

## Crypto protocol (what the hashes actually guarantee)

- `payload_hash = SHA256(canonical_json(payload))` — canonicalization: sorted keys, `,`/`:` separators, floats rounded to **6 decimal places**, datetimes → ISO-8601.
- `record_hash = SHA256(prev_hash + payload_hash)` — forward-linked chain, genesis prev = `"0"*64`.
- Ledger verification = sequence continuity + prev-pointer match + payload re-canonicalization + record-hash recompute.
- Notary artifact: Ed25519 over the SHA-256 of the canonical payload; public key embedded in artifact; verification needs no server.
- Reproducibility package hash: `SHA256(canonicalize({files: {path: sha256}}))` over the exported tree.

## Existing docs

`docs/` has per-domain specs (00–10, MASTER_SPECIFICATION, ML_METHODOLOGY) plus subdirs `ai/ cryptography/ ml/ presentation/ research/ security/ superpowers/ testing/ xai/`. The Devil's-Advocate docs land in `docs/security/` and `docs/research/`; check those subdirs for prior art before writing each.

## Gaps this phase fills (phases → deliverables)

1. Platform threat model + trust assumptions (docs/security/)
2. Research Claims Registry (docs/research/)
3. `sentinel-verify` — standalone, stdlib-only verifier CLI (scripts/sentinel_verify.py)
4. Crypto reference implementation (backend/app/cryptography/reference.py) + differential tests
5. Protocol/schema versioning in evidence artifacts
6. Property-based tests (Hypothesis) for canonicalization/hashing/chain/verifier/notary
7. Security regression corpus (backend/tests/fixtures/security/) + red-team tests
8. Mutation testing report (docs/testing/MUTATION_TESTING.md) — measured with mutmut if available
9. Database integrity audit + temporal integrity (research/db_integrity.py)
10. Devil's Advocate Report, Known Failures, Independent Reproduction Protocol
