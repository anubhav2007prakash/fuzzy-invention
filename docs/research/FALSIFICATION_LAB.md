# Falsification Lab

## Overview

The **Falsification Lab** is a research subsystem that allows researchers to deliberately attempt to disprove SentinelCrypt research claims. It provides a structured framework for designing, executing, and documenting falsification experiments with full reproducibility metadata and cryptographic evidence.

## Purpose

The purpose of the Falsification Lab is to provide a rigorous, controlled environment where researchers can:

- Select research claims to target for disproof
- Configure baseline and alternative models/datasets
- Apply controlled perturbations to data or models
- Run repeated experiments for statistical robustness
- Perform statistical analysis on results
- Determine acceptance criteria and conclusion status
- Generate reproducible evidence packages

## Conclusion Status Values

The runner reports one of these statuses using its configured practical
F1-drop thresholds. These labels are experiment-specific decisions, not
statistical-significance conclusions:

| Status | Meaning |
|---|---|
| `SUPPORTED` | The configured practical-drop criterion was not reached. |
| `PARTIALLY_SUPPORTED` | The lower end of the F1-drop interval exceeds the smaller practical-drop threshold, but not the larger threshold. |
| `NOT_SUPPORTED` | The lower end of the F1-drop interval exceeds the larger practical-drop threshold. |
| `INCONCLUSIVE` | The interval is unavailable or does not establish either configured practical-drop threshold. |

## Experiment Structure

Each falsification experiment consists of the following components:

### Claim Selection

- **claim_id**: Unique identifier for the claim (e.g., `CLAIM-001`)
- **claim_statement**: Human-readable description of the research claim

### Configuration Groups

- **baseline_configuration**: The original model/dataset configuration representing the claim
- **alternative_configuration**: The alternative model/dataset configuration used for comparison
- **alternative_dataset**: Optional FK to a different dataset for comparison

### Controlled Perturbation

- **perturbation_type**: Type of perturbation (e.g., `gaussian_noise`, `feature_dropout`)
- **perturbation_strength**: Strength of the perturbation (0.0 - 1.0)
- **perturbation_distribution**: Distribution type for noise generation

### Repeated Runs

- **n_repeats**: Number of repeated runs for statistical robustness (default: 3)
- **random_seed**: Base random seed for reproducibility

### Metrics and Analysis

- **f1_score**: Primary detection metric for comparison
- **independent bootstrap**: Baseline and perturbed alternative trials use different seeds and may use different datasets, so the runner independently resamples each group (5,000 resamples, 95% percentile interval).
- **cohens_d**: Pooled-SD effect size for alternative-minus-baseline F1; null when not estimable.
- **f1_drop**: Difference in F1 between baseline and alternative
- **raw-data provenance**: Includes both raw run groups, trial IDs and values used in the statistical comparison, raw-data references, and a canonical-observation SHA-256 digest.

No p-value, t-statistic, or significance claim is produced. With fewer than
two runs per group, the interval and effect size are unavailable. Even with
more runs, repeated seeds or a shared dataset may not be independent samples
from a target population.

### Acceptance Criteria

The runner currently applies practical F1-drop criteria:

- a lower interval bound above 0.15 produces `NOT_SUPPORTED`;
- a lower interval bound above 0.05 but not 0.15 produces `PARTIALLY_SUPPORTED`;
- otherwise the result is `INCONCLUSIVE`.

These are fixed runner rules and are not selected automatically from an
experiment's acceptance-criteria JSON. They do not imply statistical
significance.

## API Endpoints

### Claim Management

| Endpoint | Description |
|---|---|
| `POST /falsification/claims` | Create a new falsification claim |
| `GET /falsification/claims` | List all falsification claims |
| `GET /falsification/claims/{claim_id}` | Get a specific claim details |
| `POST /falsification/claims/{claim_id}/run` | Execute falsification experiment |
| `POST /falsification/claims/{claim_id}/acceptance-criteria` | Set acceptance criteria |
| `GET /falsification/conclusion-statuses` | Get valid conclusion status values |

### Request: Create Claim

```json
POST /falsification/claims
{
  "claim_id": "CLAIM-001",
  "claim_statement": "The model's detection accuracy degrades significantly under distribution shift.",
  "baseline_configuration": {"n_samples": 1200, "random_state": 42},
  "alternative_configuration": {"n_samples": 1200, "random_state": 420},
  "perturbation_configuration": {
    "perturbation_type": "gaussian_noise",
    "perturbation_strength": 0.1
  },
  "alternative_dataset_id": null,
  "n_repeats": 3,
  "random_seed": 42
}
```

### Response: Experiment Result

The result includes raw runs and an independent-trial statistical comparison.
Illustrative structure (values are omitted; no numerical result is implied):

```json
{
  "experiment_id": "exp_123",
  "claim_id": "CLAIM-001",
  "claim_statement": "The model's detection accuracy degrades significantly under distribution shift.",
  
  "configuration": {
    "baseline_configuration": {"n_samples": 1200, "random_state": 42},
    "alternative_configuration": {"n_samples": 1200, "random_state": 420},
    "perturbation_type": "gaussian_noise",
    "perturbation_strength": 0.1,
    "n_repeats": 3,
    "random_seed": 42
  },
  
  "provenance": {
    "experiment_id": "exp_123",
    "claim_id": "CLAIM-001",
    "claim_statement": "The model's detection accuracy degrades significantly under distribution shift.",
    "baseline_configuration": {"n_samples": 1200, "random_state": 42},
    "alternative_configuration": {"n_samples": 1200, "random_state": 420},
    "perturbation_config": {"perturbation_type": "gaussian_noise", "perturbation_strength": 0.1},
    "datasets": { ... },
    "random_seed": 42,
    "n_repeats": 3,
    "generated_at": "2026-01-15T10:30:00Z"
  },
  
  "raw_results": {
    "baseline": [ ... ],
    "alternative_perturbed": [ ... ]
  },
  
  "derived_metrics": {
    "baseline": { "f1_mean": 0.92, "f1_series": [0.91, 0.92, 0.93] },
    "alternative": { "f1_mean": 0.78, "f1_series": [0.77, 0.79, 0.78] },
    "difference": {
      "f1_drop": null,
      "f1_drop_confidence_interval": null,
      "cohens_d": null,
      "effect_size_method": "Cohen's d using pooled within-group trial SD",
      "statistical_analysis": {
        "design": "independent repeated trials",
        "method": "independent trial-level percentile bootstrap of difference in means",
        "confidence_level": 0.95,
        "bootstrap_resamples": 5000,
        "raw_data_refs": ["/raw_results/baseline", "/raw_results/alternative_perturbed"],
        "raw_data_sha256": "...",
        "raw_observations": {
          "baseline": [],
          "treatment": []
        },
        "p_value": null,
        "significance_claim": null
      }
    },
    "conclusion": {
      "status": "INCONCLUSIVE",
      "justification": "The interval does not establish either practical-drop threshold, or too few trial units were available; no significance claim is made.",
      "conclusion_status": "INCONCLUSIVE",
      "conclusion_labels": {
        "SUPPORTED": "SUPPORTED",
        "PARTIALLY_SUPPORTED": "PARTIALLY_SUPPORTED",
        "NOT_SUPPORTED": "NOT_SUPPORTED",
        "INCONCLUSIVE": "INCONCLUSIVE"
      }
    }
  },
  
  "plots": {
    "f1_comparison": "falsification_exp_123_f1_comparison.png",
    "perturbation_analysis": "falsification_exp_123_perturbation_analysis.png",
    "distribution_comparison": "falsification_exp_123_distribution_comparison.png"
  },
  
  "evidence": {
    "claim_id": "CLAIM-001",
    "conclusion_status": "INCONCLUSIVE",
    "configuration_hash": "sha256...",
    "provenance": { ... },
    "raw_result_files": [],
    "derivation_method": "independent_trial_percentile_bootstrap_cohens_d",
    "statistical_raw_data_refs": ["/raw_results/baseline", "/raw_results/alternative_perturbed"],
    "statistical_raw_data_sha256": "...",
    "generated_at": "2026-01-15T10:30:00Z"
  },
  
  "status": "COMPLETED",
  "generated_at": "2026-01-15T10:30:00Z"
}
```

## Frontend UI

The Falsification Lab frontend provides:

- **Claim listing**: View all registered falsification claims
- **Claim creation**: Form to create new claims with configuration
- **Experiment execution**: Run falsification experiments with live telemetry
- **Results visualization**: F1-drop estimate and bootstrap interval, pooled-SD effect size, and practical-threshold conclusion (no p-value)
- **Evidence export**: One-click evidence package export
- **Reproducibility manifest**: Display and download reproducibility packages

## Database Entities

### `falsification_experiments`

| Column | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | String | Experiment name |
| `research_question` | Text | Research question |
| `claim_id` | String (unique) | Unique claim identifier |
| `claim_statement` | Text | Human-readable claim description |
| `baseline_configuration` | JSON | Baseline model/dataset config |
| `alternative_configuration` | JSON | Alternative model/dataset config |
| `alternative_dataset_id` | UUID (FK) | Optional different dataset |
| `perturbation_type` | String | Type of perturbation |
| `perturbation_strength` | Float | Perturbation strength |
| `n_repeats` | Integer | Number of repeated runs |
| `random_seed` | Integer | Base random seed |
| `acceptance_criteria` | JSON | Acceptance criteria definition |
| `conclusion_status` | String | SUPPORTED/PARTIALLY_SUPPORTED/NOT_SUPPORTED/INCONCLUSIVE |
| `configuration_hash` | String (SHA-256) | Hash of configuration |
| `result_hash` | String (SHA-256) | Hash of result |
| `status` | String | pending/completed |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

### `falsification_results`

| Column | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `experiment_id` | UUID (FK) | Linked experiment |
| `run_index` | Integer | Which repeat (0-indexed) |
| `configuration_snapshot` | JSON | Configuration used for this run |
| `raw_data` | JSON | Raw experiment output |
| `provenance` | JSON | Provenance information |
| `derived_metrics` | JSON | Derived statistical metrics |
| `statistical_test` | String | Test used (e.g., "paired_t_test") |
| `statistical_result` | JSON | Test results (t-stat, p-value, etc.) |
| `plots` | JSON | File paths for generated plots |
| `evidence_summary` | JSON | Evidence summary |
| `conclusion_status` | String | Conclusion status |
| `conclusion_justification` | Text | Human-readable justification |
| `reproducibility_metadata` | JSON | Reproducibility metadata |
| `execution_time_s` | Float | Execution time in seconds |
| `created_at` | DateTime | Creation timestamp |

## Security

**Do not allow arbitrary code execution through the UI.**

The Falsification Lab implements the following security measures:

1. **No code execution**: All experiments use predefined, sandboxed Python functions with no user-supplied code execution
2. **Configuration-only**: Experiments are driven by JSON configuration, not arbitrary Python
3. **Dataset isolation**: Only registered, validated datasets can be used
4. **Resource limits**: Experiments have configurable `n_repeats` and resource limits
5. **Hash verification**: All results are cryptographically anchored with SHA-256 hashes
6. **No external network access**: Experiments run in isolated environment without outbound network access

## Reproducibility

Every falsification experiment produces full reproducibility metadata:

- **Random seed**: Base seed + repeat offset for deterministic reruns
- **Configuration hash**: SHA-256 of the canonical configuration
- **Result hash**: SHA-256 of the derived metrics (envelope keys stripped)
- **Git metadata**: Commit hash and branch for environment tracking
- **Environment metadata**: Python version, package versions, platform
- **One-click export**: Reproducibility package includes README, config.yaml, environment.json, results.json, metrics.csv, and verification report

## Integration with Existing System

The Falsification Lab integrates with:

- **Research Mode**: Full access in Research Mode; gated in Demo Mode
- **Cryptographic Audit**: All results anchor into the SHA-256 forward-linked hash chain
- **Provenance Graph**: Experiment nodes appear in the provenance graph for inspection
- **Trust Checklist**: Eight-point evidence checklist per experiment result
- **Existing Experiment Framework**: Reuses experiment service patterns (EXP-A through EXP-H and EXP-ROBUSTNESS)

## Development

### Adding a New Falsification Claim

1. Create a new `FalsificationExperiment` entry via `POST /falsification/claims`
2. Define the claim statement and configurations
3. Optionally set acceptance criteria via `POST /falsification/claims/{claim_id}/acceptance-criteria`
4. Run the experiment via `POST /falsification/claims/{claim_id}/run`
5. View results in the Falsification Lab frontend page

### Running a Falsification Experiment

The experiment orchestrator (`backend/app/research/falsification.py`):

1. Loads the experiment definition from the database
2. Loads baseline and alternative datasets
3. Trains models with specified configurations
4. Applies controlled perturbations
5. Evaluates metrics (F1, precision, recall, etc.)
6. Uses an independent trial-level bootstrap for the baseline-versus-alternative
   comparison and reports Cohen's d when estimable; no hypothesis test or
   significance decision is performed
7. Determines conclusion status based on acceptance criteria
8. Persists results to the database
9. Generates reproducibility metadata
10. Produces plots and evidence packages

## Example Workflow

### 1. Create a Claim

Researcher defines: "Random Forest models overfit to training data, achieving 20% higher F1 on training vs test."

```json
POST /falsification/claims
{
  "claim_id": "CLAIM-OVERFIT-001",
  "claim_statement": "Random Forest models overfit to training data, achieving 20% higher F1 on training vs test.",
  "baseline_configuration": {"n_samples": 1000, "random_state": 42},
  "alternative_configuration": {"n_samples": 1000, "random_state": 42, "perturbation_type": "gaussian_noise", "perturbation_strength": 0.1},
  "perturbation_configuration": {"perturbation_type": "gaussian_noise", "perturbation_strength": 0.1},
  "n_repeats": 5,
  "random_seed": 42
}
```

### 2. Run the Experiment

The system runs the configured number of baseline and noise-perturbed trials.
The result includes the raw trial observations, a bootstrap interval for the
difference in mean F1 when enough trials are available, and the corresponding
effect size when estimable. The groups are analyzed independently because they
can use different seeds, datasets, and perturbations.

### 3. Review Results

- **F1 drop and bootstrap interval**: computed from the experiment's raw trial
  observations; omitted or `null` when the configured trial count is
  insufficient
- **Effect size**: Cohen's d for the independent groups when estimable
- **Conclusion**: a configured practical-drop classification, not a
  statistical-significance or population-level claim

### 4. Export Evidence

Export a reproducibility package for peer review or publication.