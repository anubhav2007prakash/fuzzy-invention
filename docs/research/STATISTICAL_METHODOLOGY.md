# Statistical Methodology for SentinelCrypt Experiments

## Purpose and scope

This document defines the statistical procedures currently implemented for
repeated SentinelCrypt experiments. Statistical methods are selected from the
experimental design; the application does not automatically choose a
hypothesis test. These procedures describe variability among the configured
trials and do not, by themselves, establish a population-level guarantee,
causal effect, or scientific reproducibility.

The shared implementation is
[`statistical_analysis.py`](../../backend/app/ml/evaluation/statistical_analysis.py).
It is used by the A–E ablation study (EXP-F), falsification comparison, and
research challenge framework.
It is also used by the research challenge framework for explicitly
seed-varied longitudinal trials. Same-configuration challenge repeats and
condition sweeps in the robustness/XAI-agreement studies receive descriptive
summaries only; conditions are not treated as repeated samples. Other
experiment endpoints retain their existing metrics and are not implied to
have confidence intervals or inferential statistics unless such results are
explicitly returned with raw trial provenance.

## Statistical units and designs

### EXP-F: paired repeated trials

One trial is a complete train/test split and model fit identified by its seed.
Within each trial, all selected A–E arms share the same fitted model,
preprocessed data, held-out targets, predictions, and probabilities. The
per-metric arm comparison therefore uses a paired design with matching,
ordered trial IDs. A mismatch raises an error; the implementation never
silently truncates or reorders pairs.

For each arm, a percentile bootstrap resamples complete trial-level
observations with replacement and computes the arithmetic mean. The paired
comparison resamples paired trial differences and computes the mean
treatment-minus-baseline difference. EXP-F uses 2,000 bootstrap resamples,
95% percentile intervals, and deterministic seeds derived from the
experiment seed and metric name.

Predictive metric effect size is Cohen's dz: mean paired difference divided by
the sample standard deviation of paired differences. It is undefined (`null`)
when fewer than two pairs exist or paired differences have zero variance.
Per-arm sample variance and sample standard deviation use the usual `n - 1`
denominator and are `null` for one observation.

EXP-F cost values are summarized descriptively per arm. They are not presented
as paired causal comparisons: execution order and other measurement effects
are not randomized or controlled sufficiently to support that interpretation.
Unavailable component measurements have zero observations and `null` summary
values, not a fabricated measured zero.

### Falsification comparison: independent configured runs

The baseline and perturbed alternative can use different seeds, datasets, and
input perturbations. They are therefore analyzed as independent groups, not
paired observations. The implementation independently resamples each group's
complete trial-level F1 observations and forms the treatment-minus-baseline
difference in means. It also reports group sample variances and Cohen's d
using the pooled within-group sample standard deviation. The effect-size
direction is treatment (alternative) minus baseline; the separately named
`f1_drop` reverses that direction (baseline minus alternative).

The falsification workflow's configured practical-drop thresholds are
decision criteria for that experiment, not p-value thresholds. Its conclusion
must not be described as statistical significance. With fewer than two trials
in either group, no bootstrap interval or pooled effect size is returned.
The current implementation uses 5,000 resamples at the 95% confidence level.

### Research challenges and condition series

Challenges that explicitly vary the seed in a longitudinal design use the
trial-level percentile bootstrap for metric means, with 2,000 resamples and a
95% interval. Same-seed standard runs and reproducibility reruns are
descriptive only because they are executions of one configuration, not
independent experimental trials. Wall-clock runtime is always reported
descriptively because run order and machine load are not controlled.

Robustness curves and XAI-agreement-by-noise series compare configured
conditions (epsilon/noise levels), not repeated trial samples. Their means,
sample variances, and ranges are labeled as descriptive summaries and carry no
confidence interval.

## Raw-data traceability

Each statistic includes:

- The raw-data reference (`raw_data_ref` for a summary and `raw_data_refs` for
  a comparison).
- The exact trial IDs and metric values used (`raw_observations`).
- A SHA-256 digest of the canonical serialization of those observations.
- The procedure, confidence level, resample count, and bootstrap seed.

Descriptive condition summaries identify conditions and provide references
back to their curve entries; bootstrap trial summaries identify trial IDs. The
raw observation values are included in the returned experiment result and the
statistical result itself. Falsification persistence stores both baseline and
alternative raw runs, as well as the full statistical result, in the
database. The digest is an integrity aid for the represented observations; it
is not a signature or proof that the recorded observations are truthful.
The `$.runs[*].metric.path` references use JSONPath-style selection for
challenge run series; EXP-F and falsification references use paths within
their respective result envelopes.

The legacy `research_metrics.summarize` helper is descriptive-only and returns
no confidence interval. Its `paired_compare` wrapper requires explicit trial
IDs and raw references and delegates to the design-aware paired bootstrap; it
does not choose hypothesis tests.

## Interpretation and limitations

- A confidence interval is a bootstrap description of configured trial
  variability. With few trials it is coarse, unstable, and should not be read
  as population coverage.
- The independent bootstrap assumes independent trial units within groups.
  Repeated seeds on one fixed dataset may be correlated; the reported interval
  then describes those configured runs rather than independent samples from a
  target population.
- The paired bootstrap is appropriate only when arms are genuinely matched by
  trial ID and design. Trial identity does not make unrelated measurements
  paired.
- Percentile intervals are used as a transparent descriptive method; no
  normality assumption or automatic test selection is made.
- No p-values or significance decisions are produced by these methods.
- The metrics describe the specified data, preprocessing, configuration, and
  execution environment. They do not establish real-world detection efficacy.
- Timing and memory results are machine- and load-dependent; their intervals
  do not account for environmental drift unless it is represented by the
  repeated trial design.

## Tests

[`test_statistical_analysis.py`](../../backend/tests/unit/test_statistical_analysis.py)
checks deterministic resampling, raw-data digests and references, paired trial
identity enforcement, independent-group resampling, effect-size direction,
single-trial behavior, and invalid input rejection.
[`test_new_experiments.py`](../../backend/tests/unit/test_new_experiments.py)
checks EXP-F's stored methodology, raw references, and paired summaries.
[`test_falsification_statistics.py`](../../backend/tests/unit/test_falsification_statistics.py)
checks falsification's independent-trial analysis and persistence of both raw
trial groups alongside their derived statistics.
[`test_challenges.py`](../../backend/tests/unit/test_challenges.py) checks that
same-seed challenges remain descriptive and seed-varied longitudinal
challenges attach bootstrap summaries to their raw runs.
