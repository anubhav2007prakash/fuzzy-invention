"""Integration tests for Prediction API (/api/v1/predictions)."""
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
from backend.app.cryptography.hashing import hash_file
from backend.app.db.database import Base, get_db
from backend.app.db.repositories.dataset_repository import DatasetRepository
from backend.app.main import app
from backend.app.schemas.dataset import DatasetCreate
from backend.app.schemas.model import ModelTrainRequest
from backend.app.services.training_service import TrainingService


class TestPredictionAPI(unittest.TestCase):
    def setUp(self):
        # In-memory database with StaticPool for cross-session shared state
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

        # Temporary directory
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

        # Create training CSV & model
        np.random.seed(42)
        n_rows = 100
        df = pd.DataFrame({
            "proto": np.random.choice(["tcp", "udp"], size=n_rows),
            "service": np.random.choice(["http", "dns"], size=n_rows),
            "dur": np.random.exponential(scale=1.0, size=n_rows),
            "sbytes": np.random.randint(100, 2000, size=n_rows),
            "label": np.random.choice([0, 1], size=n_rows, p=[0.7, 0.3]),
        })
        self.csv_filename = "pred_api_flow.csv"
        df.to_csv(self.data_raw_dir / self.csv_filename, index=False)

        # Register dataset & train model
        db = self.SessionLocal()
        repo = DatasetRepository(db)
        dataset = repo.create(
            DatasetCreate(
                name="Prediction API Dataset",
                source="api_fixtures",
                file_name=self.csv_filename,
                file_hash=hash_file(str(self.data_raw_dir / self.csv_filename)),
                row_count=n_rows,
                feature_count=4,
                target_column="label",
                validation_status="VALID",
                label_distribution=json.dumps({"0": 70, "1": 30}),
            )
        )
        t_service = TrainingService(db)
        model_resp = t_service.train_model(
            ModelTrainRequest(
                dataset_id=dataset.id,
                model_type="logistic_regression",
                random_seed=42,
            )
        )
        self.model_id = model_resp.id
        db.close()

    def tearDown(self):
        app.dependency_overrides.clear()
        settings.DATA_RAW_DIR = self._orig_raw
        settings.MODELS_TRAINED_DIR = self._orig_trained
        settings.MODELS_ARTIFACTS_DIR = self._orig_artifacts
        self.temp_dir.cleanup()

    def test_single_prediction_api_lifecycle(self):
        sample = {
            "proto": "tcp",
            "service": "http",
            "dur": 0.45,
            "sbytes": 850,
        }
        res = self.client.post("/api/v1/predictions", json={"model_id": self.model_id, "features": sample})
        self.assertEqual(res.status_code, 201)
        data = res.json()
        pred_id = data["prediction_id"]
        self.assertEqual(data["model_id"], self.model_id)
        self.assertIn("input_hash", data)
        self.assertIn(data["predicted_class"], ["0", "1"])

        # Fetch prediction by ID
        fetch_res = self.client.get(f"/api/v1/predictions/{pred_id}")
        self.assertEqual(fetch_res.status_code, 200)
        fetch_data = fetch_res.json()
        self.assertEqual(fetch_data["prediction_id"], pred_id)

        # List predictions
        list_res = self.client.get("/api/v1/predictions")
        self.assertEqual(list_res.status_code, 200)
        list_data = list_res.json()
        self.assertEqual(list_data["total"], 1)

    def test_batch_prediction_api_lifecycle(self):
        samples = [
            {"proto": "tcp", "service": "http", "dur": 0.1, "sbytes": 200},
            {"proto": "udp", "service": "dns", "dur": 0.05, "sbytes": 80},
        ]
        res = self.client.post("/api/v1/predictions/batch", json={"model_id": self.model_id, "samples": samples})
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["total_samples"], 2)
        self.assertEqual(len(data["predictions"]), 2)
        self.assertGreater(data["processing_time_ms"], 0.0)


if __name__ == "__main__":
    unittest.main()
