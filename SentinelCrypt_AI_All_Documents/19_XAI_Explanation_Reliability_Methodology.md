# SentinelCrypt AI — XAI & Explanation Reliability Methodology

## Objective
Measure whether model-generated feature attributions remain reasonably stable under predefined controlled perturbations.

## Method
Use SHAP or another documented explainer appropriate to the model.

## Explanation Record
Prediction ID; model/version; explainer; attribution values; top-k features; timestamp; configuration.

## Stability Experiment
1. Generate baseline prediction/explanation.
2. Apply small predefined perturbations to permitted features.
3. Recompute prediction/explanation.
4. Calculate attribution similarity and prediction consistency.
5. Repeat over the defined sample.

## Metrics
Cosine similarity, rank correlation, top-k overlap, and prediction consistency.

## Interpretation
An explanation is an attribution produced by a model/explainer configuration; stability does not prove causal correctness or truth.

## Validity Threats
Explainer dependence, feature correlations, perturbation design, and sample size.
