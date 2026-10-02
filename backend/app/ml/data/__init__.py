"""Controlled synthetic data generation for tests and benchmarks."""
from backend.app.ml.data.synthetic import (
    generate_flow_dataset,
    generate_flow_csv,
    SYNTHETIC_DISCLAIMER,
)

__all__ = ["generate_flow_dataset", "generate_flow_csv", "SYNTHETIC_DISCLAIMER"]
