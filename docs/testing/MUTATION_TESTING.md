# Mutation testing

SentinelCrypt uses a small, deterministic Python mutation harness for selected
security-sensitive modules. The harness is intentionally scoped: it is a
regression signal for test quality, not a proof of security or a replacement
for code review, property-based testing, or threat analysis.

## Scope and test mapping

The harness mutates one source module at a time and runs only the corresponding
focused test files:

| Area | Mutated modules | Focused tests |
|---|---|---|
| Evidence and cryptography | `backend/app/cryptography/canonicalization.py`, `hash_chain.py`, `hashing.py`, `verifier.py` | `test_hashing.py`, `test_verifier.py`, `test_reference_differential.py`, `test_security_redteam.py`, `test_property_based.py` |
| Dataset validation and preprocessing | `backend/app/ml/preprocessing/validators.py`, `pipeline.py`; dataset and model request schemas | `test_file_security.py`, `test_preprocessing.py`, `test_property_based_contracts.py`, `test_security_redteam.py`, `test_api_validation.py` |
| Experiment integrity | experiment schema, API, service, and `backend/app/research/reproducibility.py` | `test_experiments.py`, `test_new_experiments.py`, `test_reproducibility.py`, `test_property_based_contracts.py`, `test_experiment_api.py` |

Mutations are limited to comparison operators, boolean operators, boolean
constants, and integer literals in executable Python code. Strings and comments
are excluded. The harness does not currently implement a dedicated hash-link
removal or filesystem/database mutation operator; those controls are only
assessed when a supported operator changes their executable logic.

The default cap is 12 evenly sampled mutants per module, chosen deterministically
from all candidates so sampling covers the source rather than only its first
lines. Set `--max-mutants 0` to run every candidate. A test failure kills a
mutant. A test pass means it survived. Pytest errors, runner errors, and
timeouts are reported separately and are not counted as kills or survivors.
The score is `killed / (killed + survived)`; error and timeout counts are
reported separately and excluded from that denominator.

## Run locally

Install the project test dependencies, then run:

```bash
python scripts/mutation_harness.py
```

Override tests for a diagnostic run with repeated `--test` options. The normal
test mapping should be preferred because each module has a distinct focused
suite. The script checks each suite is green before mutating its module and
restores each source file in a `finally` block.

On Windows, the harness itself does not require POSIX `fork`; it is a
purpose-built runner rather than Mutmut. It still requires Python, pytest, and
the dependencies used by the selected tests.

## CI and reports

`.github/workflows/mutation.yml` runs the bounded suite weekly and on manual
dispatch, not on every pull request. This keeps ordinary CI latency and compute
cost unchanged. Each run uploads `artifacts/testing/mutation-report/` even if
the runner exits nonzero. A completed report records the run timestamp,
available and executed mutations, kills, survivors, errors, timeouts, per-target
tests, and survivor details. A run with test errors or timeouts fails the CI
job; survivors are reviewed rather than hidden behind an arbitrary score gate.

## Existing measurement and limitations

The repository contained a saved crypto-only measurement of 34 generated
mutants, 27 kills, and 7 survivors (79.4%; 446 seconds). It is preserved as
`artifacts/testing/mutation-report/legacy-crypto-run.json` and is explicitly
marked historical: its earlier runner treated timeouts and unexpected errors
as kills and could count repeated tokens on a line as the same mutation. Those
counts are therefore not a reliable baseline under the corrected accounting
and do not cover dataset, API-schema, preprocessing, or experiment modules.

The current environment lacks pytest, so a corrected full run has not been
measured locally. The weekly/manual CI run will produce the first report under
the current method; no current score is claimed here. Survivors and equivalent
mutants must be inspected individually. Do not add assertions solely to raise a
score when the mutation is behaviorally equivalent or outside the stated
security contract.
