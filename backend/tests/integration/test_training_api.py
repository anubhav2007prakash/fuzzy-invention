"""Integration tests for Models and Training API (/api/v1/models)."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.app.db.database import Base, get_db
from backend.app.db.repositories.dataset_repository import DatasetRepository
from backend.app.main import app
from backend.app.schemas.dataset import DatasetCreate


from sqlalchemy.pool import StaticPool


class TestModelsAPI(unittest.TestCase):
    def setUp(self):
        # In-memory database with StaticPool so all connections share the same memory DB
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Temporary directories
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_raw_dir = Path(self.temp_dir.name) / "raw"
        self.models_dir = Path(self.temp_dir.name) / "models"
        self.artifacts_dir = Path(self.temp_dir.name) / "artifacts"
        self.data_raw_dir.mkdir(parents=True)
        self.models_dir.mkdir(parents=True)
        self.artifacts_dir.mkdir(parents=True)

        self._orig_raw = settings.DATA_RAW_DIR
        self._orig_trained = settings.MODELS_TRAINED_DIR
        self._orig_artifacts = settings.MODELS_ARTIFACTS_DIR
        settings.DATA_RAW_DIR = self.data_raw_dir
        settings.MODELS_TRAINED_DIR = self.models_dir
        settings.MODELS_ARTIFACTS_DIR = self.artifacts_dir

        # Create dummy CSV
        np.random.seed(42)
        n_rows = 100
        df = pd.DataFrame({
            "proto": np.random.choice(["tcp", "udp"], size=n_rows),
            "service": np.random.choice(["http", "dns"], size=n_rows),
            "dur": np.random.exponential(scale=1.0, size=n_rows),
            "sbytes": np.random.randint(100, 2000, size=n_rows),
            "label": np.random.choice([0, 1], size=n_rows, p=[0.7, 0.3]),
        })
        self.csv_filename = "api_test_flow.csv"
        df.to_csv(self.data_raw_dir / self.csv_filename, index=False)

        # Register dataset in DB
        db = self.SessionLocal()
        repo = DatasetRepository(db)
        self.dataset = repo.create(
            DatasetCreate(
                name="API Test Dataset",
                source="api_fixtures",
                file_name=self.csv_filename,
                file_hash="test_api_hash_999",
                row_count=n_rows,
                feature_count=4,
                target_column="label",
                validation_status="VALID",
                label_distribution=json.dumps({"0": 70, "1": 30}),
            )
        )
        self.dataset_id = self.dataset.id
        db.close()

    def tearDown(self):
        app.dependency_overrides.clear()
        settings.DATA_RAW_DIR = self._orig_raw
        settings.MODELS_TRAINED_DIR = self._orig_trained
        settings.MODELS_ARTIFACTS_DIR = self._orig_artifacts
        self.temp_dir.cleanup()

    def test_full_model_lifecycle_via_api(self):
        # 1. Train Logistic Regression
        train_payload = {
            "dataset_id": self.dataset_id,
            "model_type": "logistic_regression",
            "random_seed": 42,
            "train_ratio": 0.8,
        }
        res = self.client.post("/api/v1/models/train", json=train_payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        model_id = data["id"]
        self.assertIn("Logistic Regression", data["name"])
        self.assertIn("accuracy", data["metrics"])

        # 2. List models
        list_res = self.client.get("/api/v1/models")
        self.assertEqual(list_res.status_code, 200)
        list_data = list_res.json()
        self.assertEqual(list_data["total"], 1)
        self.assertEqual(len(list_data["models"]), 1)

        # 3. Get model details
        detail_res = self.client.get(f"/api/v1/models/{model_id}")
        self.assertEqual(detail_res.status_code, 200)
        detail_data = detail_res.json()
        self.assertEqual(detail_data["id"], model_id)

        # 4. Get model metrics
        metrics_res = self.client.get(f"/api/v1/models/{model_id}/metrics")
        self.assertEqual(metrics_res.status_code, 200)
        metrics_data = metrics_res.json()
        self.assertEqual(metrics_data["model_id"], model_id)
        self.assertIn("confusion_matrix", metrics_data)
        self.assertIn("accuracy", metrics_data["metrics"])

        # 5. Delete model
        del_res = self.client.delete(f"/api/v1/models/{model_id}")
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.json()["deleted"])

        # 6. Verify 404 after deletion
        check_res = self.client.get(f"/api/v1/models/{model_id}")
        self.assertEqual(check_res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
