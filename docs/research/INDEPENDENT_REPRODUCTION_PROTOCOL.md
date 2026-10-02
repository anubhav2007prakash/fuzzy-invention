# Independent Research Reproduction Protocol

## Purpose and scope

This guide takes a researcher from a fresh checkout to a rerun of a SentinelCrypt
experiment and independent verification of its exported evidence. It assumes no
pre-existing SentinelCrypt database, model runtime, or frontend installation.
The backend experiment API is used for execution and export; the standalone
verifier reads the resulting package from disk and does not call the API.

The repository is a research prototype. The current benchmark suite uses
generated synthetic network-flow data unless an experiment result explicitly
identifies another source. In particular, current EXP-A is a synthetic
distribution-shift experiment, not a real UNSW-NB15-to-CICIDS2017 evaluation.
The registered real datasets are future work; do not interpret a synthetic
proxy as a measurement on either real dataset. See
[`EXPERIMENT_DESIGN.md`](./EXPERIMENT_DESIGN.md) and
[`RESEARCH_CLAIMS_REGISTRY.md`](./RESEARCH_CLAIMS_REGISTRY.md) for the current
scope and limitations.

## Reproduction record

Before running anything, create a record outside the repository containing:

- experiment ID and full configuration;
- repository commit (`git rev-parse HEAD`) and whether the checkout is dirty;
- Python version and the resolved package versions;
- dataset origin, license/authorization basis, and SHA-256, when a supplied
  dataset is used;
- operating system, hardware, and run date/time (UTC);
- exported package path, package hash, and verifier result.

Use an immutable release tag or commit supplied by the study author. If the
evidence package contains a commit in `environment.json`, use that commit when
reproducing that package. A moving branch name alone is not a reproducible
source reference.

## 1. Clone the repository

```sh
git clone https://github.com/palakdim2001-eng/qwert.git
cd qwert
git checkout <study-commit-or-release-tag>
git rev-parse HEAD
git status --short
```

The final command should print no changes before the reproduction starts. Keep
the printed commit ID with the reproduction record. Do not modify the study
configuration or source files in this checkout; use a separate branch or
checkout for any exploratory changes.

## 2. Install dependencies in a clean environment

Use Python 3.10 or newer. The following creates a project-local virtual
environment and installs the backend and development/test dependencies from
the checked-out `pyproject.toml`:

```sh
python -m venv .venv
```

Activate it:

```sh
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Then install and record dependencies:

```sh
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pip check
python --version
python -m pip freeze > reproduction-requirements.txt
```

`pyproject.toml` specifies minimum dependency versions rather than a complete
platform-specific lock. The resulting `reproduction-requirements.txt` records
the exact versions resolved in this environment; retain it with the reproduction
record. For byte-for-byte comparisons, use the same Python version, operating
system, dependency resolution, and hardware as the original run where possible.
Timing and memory measurements are particularly environment-dependent.

The React frontend and Node.js are not required to execute the backend
experiments or independently verify an evidence package.

## 3. Configure the local environment

Create a local development configuration from the checked-in example:

```sh
# macOS / Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

For a local reproduction, keep `ENVIRONMENT=development` and the SQLite
`DATABASE_URL` from `.env.example`. The backend initializes the database at
startup and creates its configured data, model, and results directories.
Do not use this development configuration for an Internet-accessible
deployment. Do not put production credentials or private keys in `.env`.

Run the backend from the repository root in one terminal:

```sh
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In another terminal, check that it is responding:

```sh
curl --fail http://127.0.0.1:8000/
curl --fail http://127.0.0.1:8000/api/v1/health
```

The API documentation is available locally at
<http://127.0.0.1:8000/docs>. If the health endpoint is unavailable, resolve
startup or environment errors before proceeding. Stop the local server with
Ctrl+C when finished.

## 4. Obtain authorized datasets

No external dataset is required for the canonical EXP-F procedure below:
EXP-F generates its synthetic dataset from its recorded seed and sample count.
This is the recommended first reproduction because it does not depend on
third-party dataset access or a private download.

For an experiment that explicitly requires an external dataset:

1. Obtain the exact dataset release from its authorized publisher or
   institutional repository.
2. Confirm that your intended research and redistribution/storage use is
   allowed by its license and access terms. Do not commit or publish
   restricted files.
3. Obtain the expected SHA-256 checksum from an authoritative release manifest
   or study record when one exists. A checksum calculated only after download
   detects later changes but does not establish that the source was authentic.
4. Preserve the original downloaded file unchanged. Record its version,
   download/source reference, license, and checksum.

The current general experiment API can register and validate a CSV, but
registration does not make that dataset an input to every experiment. EXP-F
currently generates synthetic input internally. Do not claim a real-dataset
reproduction unless the selected experiment implementation and its result
manifest explicitly show that dataset was used.

## 5. Verify dataset checksums

Calculate the SHA-256 of the exact file bytes before validation or upload.

```sh
# macOS / Linux
sha256sum path/to/authorized-dataset.csv

# Windows PowerShell
Get-FileHash -Algorithm SHA256 -LiteralPath .\path\to\authorized-dataset.csv
```

Compare the result with the authoritative expected checksum, if published.
Record both values and whether they matched. If no authoritative checksum is
available, record that limitation; a locally calculated hash is an identity
fingerprint, not publisher authentication.

For the generated synthetic data used by EXP-F, record the seed and sample
count. Its generated dataset digest and experiment configuration are captured
in the result/evidence manifests; there is no downloaded file checksum to
compare.

## 6. Run validation

Run the repository test suite to check the installed backend and security
contracts before conducting the study:

```sh
python -m pytest backend/tests -v
```

For a supplied CSV, validate/register it through the dataset API. The request
below uses a CSV whose target column is named `label`; change `target_column`
to the actual target column when appropriate.

```sh
curl --fail --request POST http://127.0.0.1:8000/api/v1/datasets \
  --form "file=@path/to/authorized-dataset.csv" \
  --form "dataset_name=Authorized study dataset" \
  --form "source=Publisher and release reference" \
  --form "target_column=label"
```

The response contains `dataset_id` and a `validation` object. Require
`validation.valid` to be `true`; record the reported row count, feature count,
detected format, target column, warnings, and errors. Retrieve the registered
metadata and compare its `file_hash` to the SHA-256 calculated in step 5:

```sh
curl --fail http://127.0.0.1:8000/api/v1/datasets/<dataset_id>
```

This validates and registers a dataset in the local instance. It does not
validate licensing, prove publisher authenticity, or imply that the next
experiment consumes it. Do not continue with a failed validation or a hash
mismatch; investigate and document the cause first.

## 7. Execute an experiment

The following canonical example runs EXP-F, the A–E component ablation, on
generated synthetic data. It uses the study defaults explicitly:

```sh
curl --fail --request POST \
  http://127.0.0.1:8000/api/v1/experiments/EXP-F/run \
  --header "Content-Type: application/json" \
  --data '{"n_samples":1200,"random_state":42,"model_type":"random_forest","repeats":3,"explanation_samples":1}'
```

Save the complete response as a raw run record. The backend also writes
`results/exp_f_ablation_v2.json` under the repository's configured results
directory. Check that the response reports a completed run and retain its
experiment ID, normalized parameters, result hash, configuration hash,
statistical methodology, raw trial observations, and raw-data digests.

The experiment choices are listed by `GET /api/v1/experiments`. Other currently
registered research experiments include EXP-A through EXP-D and EXP-F through
EXP-H. Review the relevant experiment design document and source before
substituting an ID: experiment input support, output, computational cost, and
data scope differ. EXP-F's design and statistical interpretation are described
in [`ABLATION_STUDY.md`](./ABLATION_STUDY.md) and
[`STATISTICAL_METHODOLOGY.md`](./STATISTICAL_METHODOLOGY.md).

For deterministic comparisons, preserve the same experiment configuration,
code commit, dataset identity, and dependency versions. Identical seeds do not
guarantee identical timing or memory measurements across machines.

## 8. Generate results and export evidence

The run response is the experiment result. To package the stored result and
generate a portable reproducibility/evidence directory, call the export route
without a configuration override:

```sh
curl --fail --request POST \
  http://127.0.0.1:8000/api/v1/experiments/EXP-F/reproducibility-package
```

The response includes `package_path`, `files`, `file_hashes`, and
`package_hash`. By default the package is written under
`results/reproducibility/EXP-F/`. Check that the path exists and preserve the
whole directory; do not edit its contents after export. Copy the package to a
separate read-only location for verification and archival.

The package is a record of the experiment and its captured configuration,
environment, results, metrics, evidence payload, version declarations, and
file hashes. It does not necessarily contain external datasets or the
dependencies required to rerun model training. Read `dataset-manifest.json`
and `environment.json` before interpreting it.

## 9. Independently verify the exported evidence

Run the verifier against the package directory. It is an independent,
offline-capable verifier: it does not import the FastAPI application, access
the database, use the frontend, download a dataset, or load a model runtime.
Run it from a second checkout or copy the verifier script and evidence package
to an offline machine for stronger operational separation.

Human-readable output:

```sh
python scripts/sentinel_verify.py results/reproducibility/EXP-F
```

Machine-readable JSON output:

```sh
python scripts/sentinel_verify.py results/reproducibility/EXP-F --json
```

The verifier returns exit code `0` for `VERIFIED`, `1` for `FAILED`, `2` for
invalid format or usage, and `3` for an unsupported version. Treat any
non-zero exit code as a failed reproduction-verification step. Preserve the
output JSON and exit code with the package. The package verifier checks the
declared evidence structure, supported versions, artifact presence, hashes,
and supported chain/signature material where present; it does not re-run the
experiment or prove that the original input data, software host, or reported
measurements were truthful.

See [`PROTOCOL_VERSIONING.md`](../cryptography/PROTOCOL_VERSIONING.md) for
supported evidence versions and legacy compatibility rules.

## 10. Report and archive the reproduction

Archive together:

- the exported package, unchanged;
- the verifier's human-readable or JSON report and process exit code;
- the exact source commit and clean/dirty state;
- the configuration and raw API response;
- the Python version and resolved dependency inventory;
- dataset authorization/source record and checksums, if applicable;
- machine and operating-system details;
- any deviations, warnings, failed checks, or unavailability of external
  dependencies.

Compare result and configuration hashes first. If they differ, compare
configuration, code commit, dataset digest, package versions, and environment
metadata before interpreting metric differences. Floating-point behavior,
dependency versions, platform, and hardware can affect outputs. For a
scientific comparison, report raw observations and methodology, not only
aggregate metrics. Do not invent confidence intervals, significance claims,
or a successful reproduction when evidence verification or required checks
fail.

## What this protocol does not establish

- Successful package verification establishes consistency with the package's
  own declared hashes and supported rules; an untrusted package can be
  self-consistent.
- SHA-256 and a local hash chain are not distributed immutability, blockchain,
  an external timestamp, or by themselves a publisher signature.
- An exported evidence package is not a complete environment image and does
  not promise full offline retraining or scientific reproduction.
- A dataset checksum alone does not prove lawful access, provenance, or
  authenticity without a trusted reference checksum and source chain.
- A reproduction result is scoped to the recorded code, data, configuration,
  dependencies, and execution environment; it is not a guarantee of
  real-world intrusion-detection effectiveness.
