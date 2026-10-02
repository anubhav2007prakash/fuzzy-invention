# Property-Based Security Testing

## Purpose

SentinelCrypt uses Hypothesis to check invariants over generated inputs, in
addition to targeted examples and security regression tests. A property test
must state a falsifiable contract and assert it against an independent oracle
or a defined invariant; generating data by itself is not a test.

Hypothesis is a required development/test dependency (`hypothesis>=6.100.0`) in
`pyproject.toml` and `requirements.txt`. A clean test environment must install
the repository's Python requirements before collecting the property suite.
The property tests are not optional or silently skipped when Hypothesis is
missing.

## Covered invariants

| Component | Generated input | Property asserted |
|---|---|---|
| Canonical JSON | Nested JSON scalars, arrays, and string-keyed objects | Production serialization matches the independent reference representation and round-trips through JSON; object insertion order does not affect canonical bytes. |
| Hashing | Canonicalizable JSON objects and 64-character hexadecimal hash inputs | Payload digests match an independent SHA-256 oracle; record digests match `SHA-256(previous_hash || payload_hash)`. |
| Hash-chain evidence | Bounded sequences of arbitrary nested payload values | Chains constructed with contiguous sequence numbers and the prior record's digest verify; changing a committed payload without recomputing evidence is rejected. |
| API schema | Model-training seeds, in-range train ratios, and JSON-compatible hyperparameter maps | Pydantic parsing preserves valid supplied configuration values and does not silently rewrite them. This does not assert API authorization or constraints that the schema does not implement. |
| Dataset validation | Generated generic CSV rows with numeric/categorical features and class labels | Validation succeeds for parseable files; row/feature counts, target column, and class distribution match the generated source rows. |
| Preprocessing | Generated categorical training values and representative unseen inference values | Fitted encodings remain stable when applied to inference values; unseen categories map to the existing `-1` sentinel; selected feature columns exclude target/metadata and numeric/categorical partitions cover features without overlap. |
| Experiment manifests | Generated random seeds and timestamps | Changing the random seed is reported as a critical difference; changing only the timestamp is not classified as reproduction-critical. |

Tests live in:

- `backend/tests/unit/test_property_based.py`
- `backend/tests/unit/test_property_based_contracts.py`

## Running

Run the focused property suite:

```powershell
py -m pytest backend/tests/unit/test_property_based.py backend/tests/unit/test_property_based_contracts.py -q
```

Run the full backend suite:

```powershell
py -m pytest backend/tests -q
```

Hypothesis tests use bounded example counts and `derandomize=True` so generated
examples are repeatable across runs. Hypothesis still shrinks a failing input
to a minimal counterexample; its failure output should be retained with the
test report when triaging.

## Regression retention

When a property finds a defect:

1. Preserve the smallest meaningful concrete input as a normal deterministic
   regression test (`test_regression_*`) near the property or in the focused
   component test module.
2. Keep the property that found it unless the property itself was invalid.
3. Record whether the defect changed production code, a test oracle, or an
   assumption; do not disguise known failures as skipped/expected failures.
4. Confirm that the regression fails before the fix and passes after it when
   the repository/test environment permits.

The crypto property module retains concrete regressions for nested Unicode,
negative zero, and rejection of non-finite numeric values. Existing security
tests continue to cover forged signatures, malformed request bodies, path
traversal, and invalid ledger records. The property suite also explicitly tests
bounded verification claims; it does not infer external completeness from a
valid local chain.

## Scope limitations

- Generated parseable CSV values test validation summaries, not whether
  dataset labels or records are honest or free of poisoning.
- Preprocessing properties exercise feature selection and category encoders;
  they do not prove global absence of ML leakage or establish model quality.
- Manifest comparison properties test implemented comparison rules; a manifest
  is descriptive metadata, not signed provenance by itself.
- Property tests cannot validate host permissions, dependency integrity, key
  custody, clock trust, deployment authentication, filesystem race behavior,
  or database backup/restore policy. Those require separate integration and
  operational controls.
- A passing bounded Hypothesis run is evidence for the asserted properties
  over sampled inputs, not a formal proof for every possible input.
