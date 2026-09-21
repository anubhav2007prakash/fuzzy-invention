# SentinelCrypt AI Research Lab and Professor Mode Design

Date: 2026-09-21
Status: Approved for implementation planning
Scope: Two sequential milestones

## 1. Purpose

SentinelCrypt AI already has a working FastAPI backend, React frontend, four
research experiments, SHAP explainability, and a SHA-256 audit ledger. The next
step is to make those capabilities feel like a reproducible cybersecurity
research platform rather than a collection of tabs.

This design adds two milestones, built one after the other:

1. Research Lab v1: a configuration-driven experiment workspace with
   reproducibility manifests, result hashes, measurable trust dimensions, and
   portable evidence export.
2. Professor and Demo Mode: a focused presentation surface that explains the
   research pipeline and demonstrates integrity verification using real stored
   experiment outputs.

The implementation must not fabricate research results. Any metric shown in the
UI must come from an actual experiment run, stored metadata, deterministic
configuration, or clearly labeled static project context.

## 2. Current System Fit

Relevant existing modules:

- `backend/app/services/experiment_service.py` runs EXP-A through EXP-D and
  writes JSON result artifacts into `results/`.
- `backend/app/api/v1/experiments.py` exposes list, get, and run endpoints.
- `frontend/src/pages/Experiments.jsx` displays experiment cards and result
  summaries.
- `frontend/src/api/experiments.js` wraps the experiment endpoints.
- `docs/research/EXPERIMENT_DESIGN.md` and `docs/research/REPRODUCIBILITY_PROTOCOL.md`
  describe the research protocol.
- `backend/tests/unit/test_experiments.py` verifies EXP-A through EXP-D.

The design preserves the existing endpoint family and extends it in a backward
compatible way where practical.

## 3. Milestone 1: Research Lab v1

### 3.1 User Experience

The current Experiments page becomes a stronger Research Lab page. It should
allow a user to:

- Select EXP-A, EXP-B, EXP-C, or EXP-D.
- Review the research question and protocol.
- Configure supported experiment parameters before running.
- Run the experiment and see deterministic output.
- Inspect reproducibility metadata.
- Inspect result and configuration hashes.
- Inspect a trust profile made from measurable dimensions.
- Export a portable evidence package for the selected run.

The page may keep the `/experiments` route for compatibility. The sidebar label
should become `Research Lab`.

### 3.2 Supported Configuration Controls

Only expose parameters already supported by `ExperimentService`:

- EXP-A: `n_samples`, `random_state`
- EXP-B: `noise_levels`, `n_repetitions`, `random_state`
- EXP-C: `n_blocks`, `random_state`
- EXP-D: `n_samples`, `random_state`

Controls should use numeric inputs where appropriate. Noise levels can be a
comma-separated numeric input in v1, parsed into an array before submission.

Validation rules:

- Seeds must be integers.
- Sample counts, block counts, and repetitions must be positive integers.
- Noise levels must be positive finite numbers.
- Invalid frontend values should block submission and show an inline error.
- Backend service methods should remain defensive and normalize or reject
  invalid values before running expensive work.

### 3.3 Research Run Envelope

Each experiment result should be wrapped or enriched with a consistent research
run envelope:

- `experiment_id`
- `title`
- `status`
- `timestamp`
- `parameters`
- `metrics` or `comparison`
- `reproducibility`
- `run_manifest`
- `result_hash`
- `configuration_hash`
- `trust_profile`
- `evidence_package`

`run_manifest` should include:

- experiment id and title
- selected configuration
- random seed when available
- result artifact filename
- synthetic data disclaimer when applicable
- git metadata when available:
  - commit
  - branch
  - dirty worktree boolean
- execution environment:
  - Python version
  - platform
  - NumPy version
  - pandas version
  - scikit-learn version
  - SHAP version
- generated timestamp

`result_hash` is the SHA-256 hash of the canonical result payload. The hash must
be computed deterministically from the result content, not from display text.

`configuration_hash` is the SHA-256 hash of the canonical experiment
configuration.

### 3.4 Evidence Package Export

Add a backend service method and API endpoint to export an evidence package for
a selected experiment:

- Suggested endpoint: `POST /api/v1/experiments/{exp_id}/evidence`
- The endpoint should load the current result or run the experiment if no result
  exists, then write an evidence package directory.

Evidence directory:

```text
results/evidence/<experiment-id>/
  experiment.json
  metrics.json
  reproducibility-manifest.json
  verification-report.json
  README.md
```

Optional files can be added when data exists:

- `model-metadata.json`
- `dataset-metadata.json`
- `plots/`

The response should include:

- `experiment_id`
- `package_path`
- `files`
- `package_hash`
- `generated_at`

`package_hash` should be derived from a deterministic manifest of file names and
file hashes. It does not need to hash ZIP bytes in v1.

### 3.5 Trust Profile

The Trust Profile must be dimension-based, not a mysterious single score.

Dimensions:

- Detection
- Explanation Stability
- Evidence Integrity
- Reproducibility
- Data Quality

Each dimension should include:

- `label`
- `value`
- `status`
- `measurement`
- `explanation`

Rules:

- Detection derives from available F1 or accuracy metrics.
- Explanation Stability derives from EXP-B stability metrics when present.
- Evidence Integrity derives from EXP-C clean-chain and tamper detection results.
- Reproducibility derives from manifest completeness, deterministic seed, and
  presence of environment metadata and hashes.
- Data Quality is `not_evaluated` in v1 unless a selected real dataset health
  report exists. Do not invent data-quality confidence.

### 3.6 Backend Components

Keep experiment orchestration in `ExperimentService`. Add small helper methods
rather than turning each experiment into a new subsystem.

Suggested additions:

- `build_research_envelope(result, config)`
- `build_run_manifest(result, config)`
- `build_trust_profile(result)`
- `export_evidence_package(exp_id)`
- `calculate_result_hash(result)`
- `calculate_configuration_hash(config)`
- `get_git_metadata()`

These helpers should use existing cryptographic canonicalization/hashing
utilities where possible.

### 3.7 Frontend Components

Refactor `Experiments.jsx` only as much as needed for clarity.

Expected page regions:

- Experiment selection list
- Configuration panel
- Run controls
- Result summary
- Trust profile bars
- Reproducibility manifest panel
- Evidence package panel
- Synthetic-data and prototype disclaimers

Use existing visual primitives (`card`, `table`, `badge`, `btn`) and existing
Lucide icons. Keep layout dense and research-tool oriented, not marketing-like.

## 4. Milestone 2: Professor and Demo Mode

### 4.1 User Experience

Add a presentation-focused page that helps a professor understand the project in
about two minutes.

Suggested route:

- `/professor-mode`

Suggested sidebar label:

- `Professor Mode`

The page should show:

- Research Question
- Methodology
- Datasets
- Models
- XAI Method
- Cryptographic Evidence
- Experiments
- Results
- Limitations
- Future Work

The page should be clean, scannable, and built from stored experiment results
where results are numerical.

### 4.2 Demo Actions

Professor Mode should include controlled actions, but they should not mutate
real production state:

- Run or refresh EXP-C tamper demonstration.
- Show clean ledger verification status from EXP-C output.
- Show tamper scenarios and detected sequence numbers from EXP-C output.
- Link back to the Research Lab evidence package for deeper inspection.

The page can also show live counts of completed experiments by calling the
existing experiment list endpoint.

### 4.3 Presentation Summary Data

Add either:

- a dedicated endpoint: `GET /api/v1/experiments/presentation-summary`, or
- a frontend aggregation built from `experimentsApi.list()`.

Recommendation: use a dedicated backend endpoint if the summary needs stable
limitations, future-work text, and evidence status in one payload. It keeps the
frontend presentation view simple.

Presentation summary fields:

- research question
- methodology bullets
- supported datasets and current dataset status
- supported models
- XAI method
- cryptographic evidence method
- experiment summaries
- latest result highlights
- limitations
- future work

Limitations must explicitly state:

- Current experiments use synthetic data.
- The audit ledger is tamper-evident, not tamper-proof.
- SentinelCrypt AI is a research prototype, not a production IDS.

## 5. API Design

Existing endpoints remain:

- `GET /api/v1/experiments`
- `GET /api/v1/experiments/{exp_id}`
- `POST /api/v1/experiments/{exp_id}/run`

New endpoints:

- `POST /api/v1/experiments/{exp_id}/evidence`
- `GET /api/v1/experiments/presentation-summary`

Endpoint ordering must avoid treating `presentation-summary` as an experiment id
in FastAPI route matching. Define fixed literal routes before `/{exp_id}`.

## 6. Data Flow

Research Lab run:

1. User selects experiment and configuration.
2. Frontend validates inputs.
3. Frontend calls `POST /experiments/{exp_id}/run`.
4. Backend runs the deterministic experiment.
5. Backend enriches the result with manifest, hashes, and trust profile.
6. Result JSON is persisted under `results/`.
7. Frontend renders metrics, manifest, hashes, and trust dimensions.

Evidence export:

1. User clicks export evidence.
2. Frontend calls `POST /experiments/{exp_id}/evidence`.
3. Backend loads the latest result or runs the experiment if missing.
4. Backend writes the evidence directory.
5. Backend returns file list, path, timestamp, and package hash.

Professor Mode:

1. Frontend calls presentation summary endpoint.
2. Backend aggregates experiment statuses and latest highlights.
3. Frontend renders the compact research narrative.
4. Demo action runs or refreshes EXP-C and updates tamper-detection display.

## 7. Error Handling

- Unknown experiment ids return HTTP 400.
- Evidence export failures return HTTP 500 with a concise message.
- Invalid experiment configuration returns HTTP 400.
- Frontend should display inline validation messages for invalid controls.
- If no experiment has been run, Professor Mode should show `Ready to run`
  states rather than empty metrics.
- If git metadata cannot be collected, use `unknown` values without failing the
  experiment.

## 8. Testing Strategy

Backend unit tests:

- Research envelope includes required fields for each experiment.
- Result hash and configuration hash are stable for the same payload.
- Trust profile returns expected dimensions and does not invent data quality.
- Evidence export writes expected files and returns package hash.
- Presentation summary includes limitations and experiment statuses.

Frontend verification:

- `npm run build` succeeds.
- Research Lab page renders completed and ready-to-run states.
- Professor Mode route builds without runtime import errors.

Regression tests:

- Existing EXP-A to EXP-D tests continue to pass.
- Existing list/get/run experiment endpoints remain compatible with current UI.

## 9. Non-Goals

This design does not implement:

- Real UNSW-NB15 to CICIDS2017 feature mapping.
- New statistical significance tests.
- OOD detection.
- Unknown attack mode.
- Full research paper generator.
- AI research assistant.
- Digital signatures using asymmetric keys.
- ZIP archive creation for evidence packages.
- Mutation of real audit ledger records during demo mode.

Those are future milestones once Research Lab v1 and Professor Mode are stable.

## 10. Implementation Order

1. Add backend envelope, manifest, hash, and trust-profile helpers.
2. Add evidence package export helper and endpoint.
3. Add presentation summary endpoint.
4. Add backend tests.
5. Refactor Experiments page into Research Lab UI.
6. Add Professor Mode page and route.
7. Update sidebar labels.
8. Run backend tests and frontend build.

## 11. Acceptance Criteria

Research Lab v1 is complete when:

- A user can configure and run EXP-A through EXP-D from the UI.
- Each completed run displays reproducibility metadata, hashes, and trust
  profile dimensions.
- A user can export an evidence package for an experiment.
- Backend tests verify manifest, hash, trust profile, and evidence export.

Professor Mode is complete when:

- A user can open `/professor-mode`.
- The page presents the full research pipeline in a compact professor-friendly
  view.
- Numerical result highlights come from stored experiment results.
- EXP-C controlled tamper demonstration can be refreshed from the page.
- Limitations are visible and accurate.

