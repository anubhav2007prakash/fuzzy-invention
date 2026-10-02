"""Property tests for validated API inputs, datasets, preprocessing, manifests."""
from __future__ import annotations

import csv
import io

import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.ml.preprocessing.pipeline import (
    _encode_categoricals,
    _identify_columns,
)
from backend.app.ml.preprocessing.validators import validate_dataset
from backend.app.research.reproducibility import compare_manifests
from backend.app.schemas.model import ModelTrainRequest


PROPERTY_SETTINGS = settings(max_examples=60, derandomize=True, deadline=None)


@given(
    seed=st.integers(),
    train_ratio=st.floats(
        min_value=0.1, max_value=0.95, allow_nan=False, allow_infinity=False
    ),
    hyperparameters=st.dictionaries(
        st.text(max_size=12),
        st.one_of(st.integers(), st.booleans(), st.text(max_size=20)),
        max_size=6,
    ),
)
@PROPERTY_SETTINGS
def test_model_train_schema_preserves_valid_configuration(
    seed, train_ratio, hyperparameters
):
    request = ModelTrainRequest(
        dataset_id="dataset-id",
        random_seed=seed,
        train_ratio=train_ratio,
        hyperparameters=hyperparameters,
    )

    assert request.random_seed == seed
    assert request.train_ratio == train_ratio
    assert request.hyperparameters == hyperparameters


@given(
    rows=st.lists(
        st.tuples(
            st.integers(min_value=-10_000, max_value=10_000),
            st.sampled_from(["tcp", "udp", "icmp"]),
            st.integers(min_value=0, max_value=1_000_000),
            st.sampled_from(["normal", "attack"]),
        ),
        min_size=1,
        max_size=40,
    )
)
@PROPERTY_SETTINGS
def test_valid_generic_csv_summary_matches_parsed_rows(rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["duration", "protocol", "bytes", "label"])
    writer.writerows(rows)

    dataframe, report = validate_dataset(
        output.getvalue().encode("utf-8"), "generated.csv"
    )

    assert report.valid
    assert report.row_count == len(rows) == len(dataframe)
    assert report.feature_count == 3
    assert report.target_column == "label"
    assert sum(report.label_distribution.values()) == len(rows)
    assert report.label_distribution == {
        label: sum(row[3] == label for row in rows)
        for label in {row[3] for row in rows}
    }


@given(st.lists(st.sampled_from(["amber", "blue", "green"]), min_size=1, max_size=30))
@PROPERTY_SETTINGS
def test_categorical_transform_reuses_fit_mapping_and_marks_unseen(values):
    training = pd.DataFrame({"protocol": values})
    encoded_training, encoders = _encode_categoricals(training, ["protocol"])
    inference = pd.DataFrame({"protocol": [values[0], "__unseen_category__"]})

    encoded_inference, _ = _encode_categoricals(
        inference, ["protocol"], fit_encoders=encoders
    )

    assert encoded_inference["protocol"].iloc[0] == encoded_training["protocol"].iloc[0]
    assert encoded_inference["protocol"].iloc[1] == -1
    assert set(encoded_training["protocol"]).issubset(
        set(range(len(encoders["protocol"].classes_)))
    )


def test_preprocessing_identifies_features_without_target_or_metadata_columns():
    frame = pd.DataFrame({
        "id": [1, 2],
        "duration": [0.2, 0.4],
        "protocol": ["tcp", "udp"],
        "label": [0, 1],
    })

    features, numeric, categorical = _identify_columns(frame, "label")

    assert features == ["duration", "protocol"]
    assert set(numeric).isdisjoint(categorical)
    assert set(numeric) | set(categorical) == set(features)


@given(
    seed=st.integers(),
    increment=st.integers(min_value=1, max_value=1_000_000),
)
@PROPERTY_SETTINGS
def test_manifest_seed_changes_are_always_critical(seed, increment):
    baseline = {"random_seed": seed, "dataset": {"sha256": "a" * 64}}
    changed = {"random_seed": seed + increment, "dataset": {"sha256": "a" * 64}}

    comparison = compare_manifests(baseline, changed)

    assert comparison["identical"] is False
    assert comparison["environment_comparable"] is False
    assert any(item["field"] == "random_seed"
               for item in comparison["critical_differences"])


@given(st.text(max_size=50))
@PROPERTY_SETTINGS
def test_manifest_timestamp_only_difference_is_not_reproduction_critical(timestamp):
    baseline = {"random_seed": 42, "generated_at": "2026-01-01T00:00:00Z"}
    changed = dict(baseline, generated_at=timestamp)

    comparison = compare_manifests(baseline, changed)

    assert comparison["critical_differences"] == []
    assert comparison["environment_comparable"] is True
