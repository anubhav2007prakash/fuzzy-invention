"""Public-contract tests for probability calibration measurements."""
import numpy as np
import pandas as pd
import joblib
import pytest
from sklearn.model_selection import train_test_split

from backend.app.ml.calibration import (
    calibration_report,
    fit_probability_calibrator,
)
from backend.app.ml.preprocessing.pipeline import build_preprocessing_pipeline
from backend.app.services.experiment_service import (
    ExperimentService,
    KNOWN_EXPERIMENT_IDS,
)
from backend.app.ml.models.logistic_regression import LogisticRegressionDetector
from backend.app.schemas.model import ModelTrainRequest


def test_reliability_diagram_and_calibration_metrics_report_observed_frequencies():
    labels = np.array([0, 0, 1, 1])
    probabilities = np.array([0.1, 0.4, 0.6, 0.9])

    report = calibration_report(labels, probabilities, n_bins=2)

    assert report["brier_score"] == pytest.approx(0.085)
    assert report["expected_calibration_error"] == pytest.approx(0.25)
    assert report["reliability_diagram"]["bins"] == [
        {
            "lower": 0.0,
            "upper": 0.5,
            "mean_predicted_probability": pytest.approx(0.25),
            "observed_positive_frequency": 0.0,
            "sample_count": 2,
        },
        {
            "lower": 0.5,
            "upper": 1.0,
            "mean_predicted_probability": pytest.approx(0.75),
            "observed_positive_frequency": 1.0,
            "sample_count": 2,
        },
    ]


def test_sigmoid_calibrator_fits_only_given_calibration_observations():
    y_calibration = np.array([0, 0, 0, 1, 1, 1] * 10)
    probabilities = np.tile(
        np.array([[0.8, 0.2], [0.7, 0.3], [0.4, 0.6]]), (10, 1)
    )
    calibrator = fit_probability_calibrator(
        "sigmoid", y_calibration, probabilities, classes=[0, 1]
    )

    calibrated = calibrator.predict_proba(probabilities)
    assert calibrated.shape == probabilities.shape
    assert np.all(calibrated >= 0)
    assert np.all(calibrated <= 1)
    assert np.allclose(calibrated.sum(axis=1), 1.0)
    assert calibrator.configuration["method"] == "sigmoid"
    assert calibrator.configuration["fit_sample_count"] == len(y_calibration)


def test_isotonic_calibration_requires_at_least_one_thousand_calibration_rows():
    y_calibration = np.tile([0, 1], 400)
    probabilities = np.tile([[0.8, 0.2], [0.2, 0.8]], (400, 1))

    with pytest.raises(ValueError, match="1000"):
        fit_probability_calibrator(
            "isotonic", y_calibration, probabilities, classes=[0, 1]
        )


def test_isotonic_calibration_is_monotone_when_sample_threshold_is_met():
    positive_probability = np.linspace(0.001, 0.999, 1000)
    labels = (positive_probability >= 0.5).astype(int)
    probabilities = np.column_stack(
        [1.0 - positive_probability, positive_probability]
    )
    calibrator = fit_probability_calibrator(
        "isotonic", labels, probabilities, classes=[0, 1]
    )

    mapped = calibrator.predict_proba(probabilities)[:, 1]
    assert np.all(np.diff(mapped) >= -1e-12)
    assert np.all((mapped >= 0) & (mapped <= 1))


def test_training_request_accepts_only_supported_calibration_choices():
    request = ModelTrainRequest(
        dataset_id="dataset-1",
        calibration_method="sigmoid",
        calibration_fraction=0.25,
    )
    assert request.calibration_method == "sigmoid"
    assert request.calibration_fraction == 0.25
    with pytest.raises(ValueError):
        ModelTrainRequest(dataset_id="dataset-1", calibration_method="temperature")
    with pytest.raises(ValueError):
        ModelTrainRequest(dataset_id="dataset-1", calibration_fraction=0.5)


def test_legacy_model_artifact_without_calibrator_keeps_raw_prediction_behavior(tmp_path):
    detector = LogisticRegressionDetector()
    X = np.array([[-2.0], [-1.0], [1.0], [2.0]])
    y = np.array([0, 0, 1, 1])
    detector.fit(X, y)
    expected = detector.predict_proba(X)
    artifact = tmp_path / "legacy-model.joblib"
    detector.save(artifact)
    payload = joblib.load(artifact)
    payload.pop("calibrator", None)
    joblib.dump(payload, artifact)

    loaded = LogisticRegressionDetector.load(artifact)
    assert loaded.calibration_configuration == {"enabled": False, "method": "none"}
    assert np.allclose(loaded.predict_proba(X), expected)


def test_calibration_lab_is_registered_and_validates_method():
    service = ExperimentService()
    assert "EXP-CALIBRATION" in KNOWN_EXPERIMENT_IDS
    assert service.validate_experiment_config(
        "EXP-CALIBRATION", {"method": "sigmoid"}
    )["method"] == "sigmoid"
    with pytest.raises(ValueError, match="method"):
        service.validate_experiment_config(
            "EXP-CALIBRATION", {"method": "temperature"}
        )


def test_preprocessing_reserves_calibration_data_without_fitting_transformers_on_it(tmp_path):
    values = np.arange(200, dtype=float)
    frame = pd.DataFrame({
        "feature": values,
        "label": np.tile([0, 1], 100),
    })
    result = build_preprocessing_pipeline(
        frame,
        target_column="label",
        train_ratio=0.8,
        calibration_fraction=0.25,
        save_dir=tmp_path,
        scaler_type="standard",
    )

    assert len(result.X_train) == 120
    assert len(result.X_calibration) == 40
    assert len(result.X_test) == 40
    assert len(result.y_calibration) == 40
    indexes = np.arange(len(frame))
    train_indexes, _ = train_test_split(
        indexes, test_size=0.2, random_state=42, stratify=frame["label"]
    )
    fit_indexes, _ = train_test_split(
        train_indexes,
        test_size=0.25,
        random_state=43,
        stratify=frame.loc[train_indexes, "label"],
    )
    assert result.pipeline.named_steps["scaler"].mean_[0] == pytest.approx(
        frame.loc[fit_indexes, "feature"].mean()
    )


def test_calibration_experiment_reports_before_after_metrics_and_limits(monkeypatch, tmp_path):
    import backend.app.services.experiment_service as experiment_service_module

    monkeypatch.setattr(experiment_service_module, "RESULTS_DIR", tmp_path)
    service = ExperimentService()
    result = service.run_exp_calibration({
        "n_samples": 800,
        "method": "sigmoid",
        "random_state": 19,
    })

    assert result["experiment_id"] == "EXP-CALIBRATION"
    assert result["parameters"]["method"] == "sigmoid"
    assert result["metrics"]["before"]["brier_score"] is not None
    assert result["metrics"]["after"]["brier_score"] is not None
    assert result["metrics"]["before"]["reliability_diagram"]["bins"]
    assert result["metrics"]["after"]["reliability_diagram"]["bins"]
    assert result["metrics"]["calibration_configuration"]["method"] == "sigmoid"
    assert "not automatically equivalent" in result["interpretation"].lower()
