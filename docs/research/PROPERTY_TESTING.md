# Property-Based Testing — Plan for the Cryptographic Core

Status: **IN PROGRESS** · Hypothesis is installed; the suite below is written and
passing on the *current* source; it becomes the CI gate once protocol hardening
is complete.

## Why

Mutation testing showed that some canonicalization invariants are only guarded
by the reference implementation or by ASCII-only payloads. Property-based
testing (Hypothesis) attacks *all* inputs, not the curated ones, and converts
guardianship into a computable score.

## Hypothesis strategies

```python
# backend/tests/unit/test_property_based.py  (written, passing)
STR = st.text(max_size=40, blacklist_categories={...})
NUM = st.floats(allow_nan=False, allow_infinity=False, width=64) | st.integers()
VALUE = st.recursive(SIMPLE, lambda c: st.lists(c, max_size=6) | st.dictionaries(...))
PAYLOAD = st.recursive(VALUE, max_leaves=12)
```

Strategy shapes: `None`, bool, int, float, str (incl. unicode), list,
dict (nested), Decimal → float (canonical serializer converts).

## Properties under test (all against `canonicalize` vs `reference.ref_canonical_json`)

| # | Property | What it proves |
|---|---|---|
| P1 | `canonicalize(x) == ref(x)` for any JSON-shaped x | canonicalization ≡ hand-written oracle |
| P2 | digests invariant under dict construction order | `sort_keys` correctness for arbitrary nesting |
| P3 | `SHA256(prev + payload_hash)` identical in both implementations | chain formula |
| P4 | any honestly built chain verifies in both implementations | chain correctness under *random* shapes |
| P5 | any *single* tampered payload breaks verification | chain tamper detection under random shapes |

## Properties P6/P7 (planned, blocked on protocol hardening)

| # | Property | Why blocked |
|---|---|---|
| P6 | non-finite floats reject | `ValueError` emitted only after canonicalization hardening landed; suite needs re-run and the CLI's canonicalizer must be aligned |
| P7 | Unicode canonical forms agree | ensure_ascii settings agreed in production + reference; proof needs a Unicode payload in the property suite |

## Acceptance

* `python -m pytest backend/tests/unit/test_property_based.py -q` → **0 failed**
* CI adds the file to the crypto mutation-testing gate.

## Measurement loop

1. Run mutation harness → record score.
2. Add property suite → re-run harness → compare score.
3. Target: ≥ 90 % score *and* no surviving mutant whose semantics changed.
