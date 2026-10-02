# Prediction Calibration Laboratory

## Purpose and scope

`EXP-CALIBRATION` measures whether predicted positive-class probabilities correspond to observed positive frequencies on a held-out sample. It compares an estimator's raw probabilities with probabilities transformed by a post-hoc calibration mapping. The synthetic experiment is deterministic for a fixed sample count and seed, and runs offline.

The experiment is descriptive. It does not establish that a model is calibrated for operational traffic, under distribution shift, or for any population not represented by its evaluation data. A raw model probability is not automatically real-world confidence.

## Run the study

From the Research Lab dashboard select **EXP-CALIBRATION**, choose the method, sample count (400–20,000), and seed, then run it. The same experiment can be invoked through the generic experiment API with:

`POST /api/v1/experiments/EXP-CALIBRATION/run` accepts this JSON body:

```json
{
  "method": "sigmoid",
  "n_samples": 1200,
  "random_state": 42
}
```

The experiment separates rows into model-fit, calibration, and held-out-test partitions. Preprocessing is fitted on model-fit rows only. The estimator and calibrator do not see the held-out test labels during fitting. Both reported calibration results use the identical held-out test observations.

## Measurements

- **Reliability diagram**: uniform-width bins of predicted positive-class probability compared with observed positive frequency. Every bin includes its sample count; empty bins have null values.
- **Brier score**: mean squared error of the positive-class probabilities against binary outcomes; lower is better for this score.
- **Expected calibration error (ECE)**: sample-weighted absolute gap between mean predicted probability and observed positive frequency across the displayed uniform-width bins; lower is better for this score.

ECE depends on the binning scheme and is not a standalone proof of calibration. A reliability diagram can be noisy when bins have few observations; inspect bin counts and the held-out sample size.

## Supported mappings and eligibility

- **Sigmoid (Platt-style)**: logistic regression on the log-odds of the estimator's predicted positive-class probability. Requires at least 50 calibration observations and at least 10 from each class.
- **Isotonic**: non-parametric monotone mapping. Enabled only with at least 1,000 reserved calibration observations because a flexible mapping with less support is prone to overfitting.

Both methods are currently limited to binary targets encoded as classes 0 and 1. Unsupported targets and insufficient calibration data fail explicitly rather than silently falling back to raw probabilities.

The thresholds are minimum eligibility gates, not assurances of statistical precision. Users should consider the dataset size, class balance, intended use, and validation design before selecting a method.

## Calibrating a trained model

Model training accepts optional fields:

```json
{
  "calibration_method": "sigmoid",
  "calibration_fraction": 0.2
}
```

`calibration_fraction` is the fraction of the model-training partition reserved for calibration (strictly between 0 and 0.5). The calibration partition is split off before categorical encoders, imputation, or scaling are fitted, so those transforms are learned from model-fit data only. The final held-out test partition is untouched by both fitting steps.

The fitted mapping is serialized with the model artifact and applied by `predict_proba` after loading. Older model artifacts without a calibrator remain loadable and return their original estimator probabilities. Training metadata records the method, calibration support, evaluation partition, Brier score, ECE, and reliability-bin counts. Calibration measurements are available from the model metrics response and dashboard.

When training without a calibration method, binary models still record raw-probability calibration measurements on the held-out evaluation split; the model remains uncalibrated. Multiclass calibration is reported as unavailable, not approximated with a binary measure.

## Interpretation and limitations

- Calibration is conditional on the data-generating distribution and evaluation design.
- A lower Brier score or ECE on a finite held-out sample does not guarantee improvement on future data.
- The held-out scores are post-selection evaluation if users repeatedly tune methods against the same test set; use a new independent evaluation sample for confirmatory claims.
- Neither the calibration experiment nor a calibrated score establishes causal validity, scientific reproducibility, or operational decision safety.
- Monitor calibration after deployment and re-evaluate when data or prevalence shifts; the current training flow does not automatically monitor or recalibrate deployed models.
