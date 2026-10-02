"""Regression tests for design-aware falsification statistics and persistence."""
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd

from backend.app.research import falsification


class _Session:
    def __init__(self, experiment):
        self.experiment = experiment
        self.added = []

    def get(self, model, experiment_id):
        assert experiment_id == self.experiment.id
        return self.experiment

    def add(self, record):
        self.added.append(record)

    def commit(self):
        pass

    def refresh(self, record):
        pass


def test_falsification_persists_independent_statistics_and_both_raw_groups(monkeypatch):
    experiment = SimpleNamespace(
        id="experiment-1",
        claim_id="CLAIM-TEST",
        claim_statement="The measured F1 remains stable under perturbation.",
        random_seed=42,
        alternative_dataset_id=None,
        status="pending",
    )
    session = _Session(experiment)

    def synthetic_frame(n_samples=1000, random_state=42, **_kwargs):
        rng = np.random.RandomState(random_state)
        signal = rng.normal(size=min(n_samples, 120))
        labels = (signal > 0).astype(int)
        return pd.DataFrame({
            "signal": signal + rng.normal(0, 0.2, size=len(signal)),
            "noise": rng.normal(size=len(signal)),
            "label": labels,
        })

    monkeypatch.setattr(falsification, "generate_flow_dataset", synthetic_frame)
    result = falsification.run_falsification_experiment(
        experiment_id=experiment.id,
        baseline_config={"model": "random_forest"},
        alternative_config={"model": "random_forest"},
        perturbation_config={
            "perturbation_type": "gaussian_noise",
            "perturbation_strength": 0.1,
        },
        n_repeats=2,
        db=session,
    )

    comparison = result["derived_metrics"]["difference"]["statistical_analysis"]
    assert comparison["design"] == "independent repeated trials"
    assert comparison["n_baseline"] == comparison["n_treatment"] == 2
    assert comparison["confidence_interval"] is not None
    assert comparison["p_value"] is None
    assert comparison["significance_claim"] is None
    assert comparison["raw_data_refs"] == [
        "/raw_results/baseline",
        "/raw_results/alternative_perturbed",
    ]

    persisted = session.added[0]
    raw_data = json.loads(persisted.raw_data)
    stored_statistics = json.loads(persisted.statistical_result)
    assert len(raw_data["baseline"]) == 2
    assert len(raw_data["alternative_perturbed"]) == 2
    assert stored_statistics["raw_data_sha256"] == comparison["raw_data_sha256"]
    assert persisted.statistical_test == "independent_trial_percentile_bootstrap"
