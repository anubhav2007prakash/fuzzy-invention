"""Integration tests for Phase 5: Explanations API (/api/v1/explanations).

Tests:
    - POST /api/v1/explanations/{prediction_id}   — generate explanation
    - GET  /api/v1/explanations/{prediction_id}   — retrieve stored explanation
    - GET  /api/v1/explanations/                  — list explanations
    - POST /api/v1/explanations/stability/{id}    — standalone stability run
    - 404 for unknown prediction_id
    - ExplanationResponse.limitations disclaimer present
    - Stability score in valid range

DISCLAIMER:
    Tests verify correct API behaviour and schema shapes.  SHAP values computed
    here reflect the trained model's decision boundary, not causal ground truth.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings
from backend.app.db.database import Base, get_db
from backend.app.db.repositories.dataset_repository import DatasetRepository
from backend.app.main import app
from backend.app.schemas.dataset import DatasetCreate


def _build_features() -> dict:
    """Build a small feature dict matching the test CSV schema."""
    return {
        "proto": "tcp",
        "service": "http",
        "dur": 0.5,
        "sbytes": 500,
    }


class TestExplanationsAPI(unittest.TestCase):
    """Full API-layer integration tests for the /api/v1/explanations endpoints."""

    def setUp(self):
        # ── In-memory SQLite with StaticPool ─────────────────────────────────
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # ── Temp directories ─────────────────────────────────────────────────
        self.temp_dir = tempfile.TemporaryDirectory()
        raw_dir = Path(self.temp_dir.name) / "raw"
        models_dir = Path(self.temp_dir.name) / "models"
        artifacts_dir = Path(self.temp_dir.name) / "artifacts"
        raw_dir.mkdir(parents=True)
        models_dir.mkdir(parents=True)
        artifacts_dir.mkdir(parents=True)

        self._orig_raw = settings.DATA_RAW_DIR
        self._orig_trained = settings.MODELS_TRAINED_DIR
        self._orig_artifacts = settings.MODELS_ARTIFACTS_DIR
        settings.DATA_RAW_DIR = raw_dir
        settings.MODELS_TRAINED_DIR = models_dir
        settings.MODELS_ARTIFACTS_DIR = artifacts_dir

        # ── Dummy CSV ─────────────────────────────────────────────────────────
        np.random.seed(42)
        n_rows = 120
        df = pd.DataFrame({
            "proto":   np.random.choice(["tcp", "udp"], size=n_rows),
            "service": np.random.choice(["http", "dns"], size=n_rows),
            "dur":     np.random.exponential(scale=1.0, size=n_rows),
            "sbytes":  np.random.randint(100, 2000, size=n_rows),
            "label":   np.random.choice([0, 1], size=n_rows, p=[0.7, 0.3]),
        })
        csv_name = "xai_test_flow.csv"
        df.to_csv(raw_dir / csv_name, index=False)

        # ── Register dataset ─────────────────────────────────────────────────
        db = self.SessionLocal()
        repo = DatasetRepository(db)
        dataset = repo.create(
            DatasetCreate(
                name="XAI Integration Dataset",
                source="xai_fixtures",
                file_name=csv_name,
                file_hash="xai_test_hash_001",
                row_count=n_rows,
                feature_count=4,
                target_column="label",
                validation_status="VALID",
                label_distribution=json.dumps({"0": 84, "1": 36}),
            )
        )
        self.dataset_id = dataset.id
        db.close()

        # ── Train a model via API ─────────────────────────────────────────────
        train_res = self.client.post(
            "/api/v1/models/train",
            json={
                "dataset_id": self.dataset_id,
                "model_type": "logistic_regression",
                "random_seed": 42,
                "train_ratio": 0.8,
            },
        )
        self.assertEqual(
            train_res.status_code, 201, f"Training failed: {train_res.text}"
        )
        self.model_id = train_res.json()["id"]

        # ── Make a prediction to get a prediction_id ─────────────────────────
        pred_res = self.client.post(
            "/api/v1/predictions",
            json={
                "model_id": self.model_id,
                "features": _build_features(),
            },
        )
        self.assertEqual(
            pred_res.status_code, 201, f"Prediction failed: {pred_res.text}"
        )
        self.prediction_id = pred_res.json()["prediction_id"]

    def tearDown(self):
        app.dependency_overrides.clear()
        settings.DATA_RAW_DIR = self._orig_raw
        settings.MODELS_TRAINED_DIR = self._orig_trained
        settings.MODELS_ARTIFACTS_DIR = self._orig_artifacts
        self.temp_dir.cleanup()

    # ── POST /explain/{prediction_id} ─────────────────────────────────────────

    def test_explain_returns_201(self):
        res = self.client.post(
            f"/api/v1/explanations/{self.prediction_id}",
            json={"features": _build_features(), "compute_stability": False},
        )
        self.assertEqual(res.status_code, 201, res.text)

    def test_explain_response_schema(self):
        res = self.client.post(
            f"/api/v1/explanations/{self.prediction_id}",
            json={"features": _build_features(), "compute_stability": False},
        )
        data = res.json()
        self.assertEqual(data["prediction_id"], self.prediction_id)
        self.assertIn("method", data)
        self.assertIn("top_features", data)
        self.assertIn("limitations", data)
        self.assertIn("created_at", data)

    def test_explain_limitations_disclaimer_present(self):
        """Every ExplanationResponse must carry the non-causal disclaimer."""
        res = self.client.post(
            f"/api/v1/explanations/{self.prediction_id}",
            json={"features": _build_features(), "compute_stability": False},
        )
        limitations = res.json()["limitations"]
        self.assertIsInstance(limitations, list)
        self.assertGreater(len(limitations), 0)
        combined = " ".join(limitations).lower()
        self.assertIn("not causal", combined)

    def test_explain_top_features_are_list(self):
        res = self.client.post(
            f"/api/v1/explanations/{self.prediction_id}",
            json={"features": _build_features(), "compute_stability": False},
        )
        self.assertIsInstance(res.json()["top_features"], list)

    def test_explain_top_k_parameter_respected(self):
        """top_k=2 should return at most 2 features."""
        res = self.client.post(
            f"/api/v1/explanations/{self.prediction_id}",
            json={
                "features": _build_features(),
                "compute_stability": False,
                "top_k": 2,
            },
        )
        self.assertEqual(res.status_code, 201, res.text)
        self.assertLessEqual(len(res.json()["top_features"]), 2)

    def test_explain_with_stability(self):
        res = self.client.post(
            f"/api/v1/explanations/{self.prediction_id}",
            json={
                "features": _build_features(),
                "compute_stability": True,
                "n_repetitions": 5,
                "noise_std": 0.05,
            },
        )
        self.assertEqual(res.status_code, 201, res.text)
        data = res.json()
        self.assertIsNotNone(data["stability_score"])
        self.assertGreaterEqual(data["stability_score"], -1.0)
        self.assertLessEqual(data["stability_score"], 1.0)

    def test_explain_without_features_body_uses_zero_vector(self):
        """Calling with no features falls back to zero-vector reconstruction."""
        res = self.client.post(
            f"/api/v1/explanations/{self.prediction_id}",
            json={"compute_stability": False},
        )
        self.assertEqual(res.status_code, 201, res.text)
        self.assertIn("top_features", res.json())

    def test_explain_without_body(self):
        """POST with no body at all (default ExplainRequest) should succeed."""
        res = self.client.post(f"/api/v1/explanations/{self.prediction_id}")
        self.assertEqual(res.status_code, 201, res.text)

    def test_explain_unknown_prediction_returns_404(self):
        res = self.client.post(
            "/api/v1/explanations/00000000-0000-0000-0000-000000000000",
            json={"features": _build_features(), "compute_stability": False},
        )
        self.assertEqual(res.status_code, 404)

    # ── GET /explain/{prediction_id} ──────────────────────────────────────────

    def test_get_explanation_after_post(self):
        # Generate first
        self.client.post(
            f"/api/v1/explanations/{self.prediction_id}",
            json={"features": _build_features(), "compute_stability": False},
        )
        # Then retrieve
        res = self.client.get(f"/api/v1/explanations/{self.prediction_id}")
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["prediction_id"], self.prediction_id)

    def test_get_explanation_not_found(self):
        res = self.client.get(
            "/api/v1/explanations/00000000-0000-0000-0000-000000000001"
        )
        self.assertEqual(res.status_code, 404)

    # ── GET /explain/ ─────────────────────────────────────────────────────────

    def test_list_explanations_empty(self):
        res = self.client.get("/api/v1/explanations/")
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertIn("explanations", data)
        self.assertIn("total", data)

    def test_list_explanations_after_explain(self):
        self.client.post(
            f"/api/v1/explanations/{self.prediction_id}",
            json={"features": _build_features(), "compute_stability": False},
        )
        res = self.client.get("/api/v1/explanations/")
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(len(data["explanations"]), 1)

    def test_list_explanations_pagination(self):
        self.client.post(
            f"/api/v1/explanations/{self.prediction_id}",
            json={"features": _build_features(), "compute_stability": False},
        )
        res = self.client.get("/api/v1/explanations/?skip=0&limit=1")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertLessEqual(len(data["explanations"]), 1)

    # ── POST /explain/stability/{prediction_id} ───────────────────────────────

    def test_stability_endpoint_returns_200(self):
        res = self.client.post(
            f"/api/v1/explanations/stability/{self.prediction_id}",
            json={"n_repetitions": 5, "noise_std": 0.05},
        )
        self.assertEqual(res.status_code, 200, res.text)

    def test_stability_response_schema(self):
        res = self.client.post(
            f"/api/v1/explanations/stability/{self.prediction_id}",
            json={"n_repetitions": 5, "noise_std": 0.05},
        )
        data = res.json()
        self.assertIn("prediction_id", data)
        self.assertIn("stability_score", data)
        self.assertIn("n_repetitions", data)
        self.assertIn("noise_std", data)
        self.assertIn("disclaimer", data)

    def test_stability_score_in_valid_range(self):
        res = self.client.post(
            f"/api/v1/explanations/stability/{self.prediction_id}",
            json={"n_repetitions": 5, "noise_std": 0.05},
        )
        score = res.json()["stability_score"]
        if score is not None:
            self.assertGreaterEqual(score, -1.0)
            self.assertLessEqual(score, 1.0)

    def test_stability_disclaimer_in_response(self):
        res = self.client.post(
            f"/api/v1/explanations/stability/{self.prediction_id}",
            json={"n_repetitions": 3, "noise_std": 0.05},
        )
        disclaimer = res.json()["disclaimer"].lower()
        self.assertIn("causal", disclaimer)

    def test_stability_endpoint_404_unknown(self):
        res = self.client.post(
            "/api/v1/explanations/stability/00000000-0000-0000-0000-000000000099",
            json={"n_repetitions": 3},
        )
        self.assertEqual(res.status_code, 404)

    def test_stability_with_features(self):
        res = self.client.post(
            f"/api/v1/explanations/stability/{self.prediction_id}",
            json={
                "features": _build_features(),
                "n_repetitions": 5,
                "noise_std": 0.01,
            },
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertIsNotNone(res.json()["stability_score"])


if __name__ == "__main__":
    unittest.main()
