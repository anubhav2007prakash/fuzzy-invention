# EXP-ROBUSTNESS: Offline Sensitivity Laboratory

## Purpose

EXP-ROBUSTNESS measures how a fitted classifier's predictions, confidence,
explanations, and held-out metrics change under small, controlled perturbations
of a synthetic feature dataset. It is a sensitivity study, not an external
system attack and not a claim that SentinelCrypt or a model is robust.

## Running the experiment

Use the Experiments dashboard or submit a JSON configuration to:

```http
POST /api/v1/experiments/EXP-ROBUSTNESS/run
Content-Type: application/json
```

Example:

```json
{
  "n_samples": 800,
  "n_probe": 12,
  "epsilon_levels": [0.02, 0.05, 0.1],
  "n_repeats": 3,
  "model_type": "random_forest",
  "with_explanations": true,
  "random_state": 42
}
```

All data are generated locally by the controlled synthetic-flow fixture. The
runner does not load external datasets, contact remote services, or probe
external systems. Each run is persisted as `results/exp_robustness.json` and is
available through the common experiment listing and evidence-export endpoints.

## Experimental procedure

For each repeat, the runner makes a stratified training/holdout split using the
configured seed plus the repeat index. A `StandardScaler` is fitted on that
repeat's training partition only and applied to both partitions. The selected
classifier is trained on the transformed training partition.

For each epsilon condition and repeat, independent, seeded uniform noise is
added to every transformed holdout feature. A feature's perturbation magnitude
is bounded by `epsilon × (training maximum − training minimum)` for that
feature. Holdout samples are not clipped to the training bounds: clipping could
alter a naturally out-of-range holdout value by more than the perturbation
budget, including at a zero-noise baseline. The recorded maximum observed
feature displacement is checked against the configured epsilon.

Metrics are computed on the complete holdout partition. Prediction agreement,
confidence change, and optional SHAP explanation similarity are computed for a
deterministically selected probe subset. Explanation failures are surfaced as
run failures rather than converted into missing-success values.

## Measurements and interpretation

Each epsilon condition reports repeat-level raw observations and descriptive
summaries for:

- prediction stability/agreement (and its complementary flip rate);
- absolute change in maximum predicted class confidence;
- optional cosine similarity of per-sample SHAP attribution vectors;
- maximum observed perturbation as a fraction of training feature range;
- clean-versus-perturbed accuracy, precision, recall, F1, macro-F1, PR-AUC,
  ROC-AUC, Brier score, and expected calibration error deltas.

The full per-repeat baseline metrics, perturbed metrics, and metric deltas are
included in the result so summary values have an auditable raw-data source.
Summaries are descriptive across repeated randomized partitions of one fixed
synthetic fixture. They do not include significance tests or population-level
confidence intervals; the partitions reuse the same generated dataset and
should not be treated as independent samples from a real-world population.

## Limits

- Synthetic fixtures do not establish performance on authorized real datasets.
- Bounded coordinate-wise noise does not cover all plausible distribution
  shifts, corruptions, data-quality faults, or adversarial strategies.
- Probe-subset explanation measurements do not characterize every explanation
  or explain causal behavior.
- A finite set of epsilon values is not a formal robustness certificate.
- Reported behavior is specific to the chosen model, synthetic generator,
  preprocessing, seeds, and configuration.
- Passing this experiment does not imply a security guarantee.

