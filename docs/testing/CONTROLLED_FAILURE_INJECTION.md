# Controlled Failure Injection

SentinelCrypt's failure-injection tools live under `backend/tests/failure_injection/`.
They are test utilities, not application features: production modules do not
import them, and there is no environment flag or API for enabling injected
failures in a running service.

## Scenarios

`backend/tests/integration/test_controlled_failure_injection.py` exercises:

| Failure | Injection method | Required observations |
|---|---|---|
| Database unavailable | In-memory SQLAlchemy session failure and a FastAPI dependency override | A structured error is returned; existing records and database integrity remain valid |
| Model artifact missing | Temporary model-registry loader patch | Prediction and explanation do not return fabricated outputs or append invalid evidence |
| Dataset corruption | Malformed upload bytes and temporary-file tampering | Validation/training rejects the input and does not register a model |
| Audit record corruption | Mutate in-memory records inside a restoring context | Ledger verification fails while unmodified records remain unchanged |
| SHAP failure | Temporary patch of the explainer method | Explanation fails explicitly and no invalid explanation is persisted |
| Incomplete experiment | Temporary runner patch and isolated result directory | No completed result is emitted and a pre-existing test result is unchanged |
| Missing configuration | Temporary settings override | The consuming operation reports the missing resource; the setting is restored |
| Unavailable dependency | Temporary import hook for one named module | The affected optional behavior reports/degrades explicitly; imports are restored |
| Invalid API request/response | Invalid identifiers, malformed JSON, invalid experiment parameters, and a patched route returning a schema-invalid success payload | Requests return structured client errors; invalid server responses fail closed with a structured 500 error and leave database state consistent |

## Isolation and restoration

- Integration tests use an in-memory SQLite database and temporary dataset,
  model, preprocessor, and experiment-result directories.
- Files modified to simulate corruption are placed in pytest `tmp_path`
  directories and restored when the injection context exits.
- Monkey-patches, settings changes, dependency overrides, and import hooks are
  scoped to context managers or the integration fixture. Injectors attempt
  cleanup even when activation raises; an injector cannot be entered twice
  while active.
- Unsupported failure names and targets outside the fixture are rejected
  rather than silently doing nothing.
- These tests must not be repointed at user datasets, shared databases, or
  production artifact directories.

## Invariant checks

The shared assertions in `failure_injection/assertions.py` check that:

- expected failures are actual failures of explicitly allowed types, not
  successful calls or arbitrary exceptions;
- HTTP failures carry a structured error or a non-empty detail;
- outcomes do not look successful or omit an explicit failure status/error;
- every baseline audit sequence is still present and unchanged, there are no
  duplicate sequence numbers, and both the baseline and post-failure ledgers
  verify;
- the database integrity auditor reports no inconsistency and requested count
  checks name real audited entities.

The verification report starts each scenario as unverified. Callers must set
all required invariant results from observations before a record counts as
passed; merely listing scenarios cannot produce a successful report.

## Running

From the repository root in PowerShell:

```powershell
python -m pytest backend/tests/unit/test_failure_injection_framework.py -q
python -m pytest backend/tests/integration/test_controlled_failure_injection.py -q
```

Run the complete backend suite with:

```powershell
python -m pytest backend/tests -q
```

Failure-injection tests can depend on optional ML packages used by the
integration fixtures. A missing test dependency is an environment/setup
failure, not evidence that a scenario passed.
