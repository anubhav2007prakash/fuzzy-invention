"""Integration tests for TrainingService, ModelRegistry, and ModelRepository."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.app.core.exceptions import DatasetNotFoundError, ModelNotFoundError
from backend.app.db.database import Base
from backend.app.db.models import Dataset
from backend.app.db.repositories.dataset_repository import DatasetRepository
from backend.app.db.repositories.model_repository import ModelRepository
from backend.app.schemas.dataset import DatasetCreate
from backend.app.schemas.model import ModelTrainRequest
from backend.app.services.training_service import TrainingService


class TestTrainingService(unittest.TestCase):
    def setUp(self):
        # Create an in-memory SQLite database for isolated test execution
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        # Temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_raw_dir = Path(self.temp_dir.name) / "raw"
        self.models_dir = Path(self.temp_dir.name) / "models"
        self.artifacts_dir = Path(self.temp_dir.name) / "artifacts"
        self.data_raw_dir.mkdir(parents=True)
        self.models_dir.mkdir(parents=True)
        self.artifacts_dir.mkdir(parents=True)

        # Monkey-patch config settings paths for tests
        self._orig_raw = settings.DATA_RAW_DIR
        self._orig_trained = settings.MODELS_TRAINED_DIR
        self._orig_artifacts = settings.MODELS_ARTIFACTS_DIR
        settings.DATA_RAW_DIR = self.data_raw_dir
        settings.MODELS_TRAINED_DIR = self.models_dir
        settings.MODELS_ARTIFACTS_DIR = self.artifacts_dir

        # Create synthetic CSV dataset file
        np.random.seed(42)
        n_rows = 120
        df = pd.DataFrame({
            "proto": np.random.choice(["tcp", "udp", "icmp"], size=n_rows),
            "service": np.random.choice(["http", "dns", "ftp"], size=n_rows),
            "dur": np.random.exponential(scale=2.0, size=n_rows),
            "sbytes": np.random.randint(100, 5000, size=n_rows),
            "dbytes": np.random.randint(100, 5000, size=n_rows),
            "label": np.random.choice([0, 1], size=n_rows, p=[0.6, 0.4]),
        })
        self.csv_filename = "synthetic_train_test.csv"
        df.to_csv(self.data_raw_dir / self.csv_filename, index=False)

        # Register dataset in DB
        repo = DatasetRepository(self.db)
        self.dataset = repo.create(
            DatasetCreate(
                name="Synthetic Flow Dataset",
                source="test_fixtures",
                file_name=self.csv_filename,
                file_hash="dummy_hash_12345",
                row_count=n_rows,
                feature_count=5,
                target_column="label",
                validation_status="VALID",
                label_distribution=json.dumps({"0": 72, "1": 48}),
            )
        )

        self.service = TrainingService(self.db)

    def tearDown(self):
        self.db.close()
        # Restore settings
        settings.DATA_RAW_DIR = self._orig_raw
        settings.MODELS_TRAINED_DIR = self._orig_trained
        settings.MODELS_ARTIFACTS_DIR = self._orig_artifacts
        self.temp_dir.cleanup()

    def test_train_logistic_regression(self):
        req = ModelTrainRequest(
            dataset_id=self.dataset.id,
            model_type="logistic_regression",
            random_seed=42,
            train_ratio=0.8,
        )
        resp = self.service.train_model(req)

        self.assertIsNotNone(resp.id)
        self.assertIn("Logistic Regression", resp.name)
        self.assertTrue(Path(resp.artifact_path).exists())
        self.assertTrue(Path(resp.preprocessing_path).exists())
        self.assertIn("accuracy", resp.metrics)
        self.assertIn("f1_macro", resp.metrics)

        # Verify DB persistence
        model_in_db = self.service.get_model(resp.id)
        self.assertEqual(model_in_db.id, resp.id)

    def test_train_random_forest(self):
        req = ModelTrainRequest(
            dataset_id=self.dataset.id,
            model_type="random_forest",
            hyperparameters={"n_estimators": 10, "max_depth": 3},
            random_seed=42,
            train_ratio=0.8,
        )
        resp = self.service.train_model(req)

        self.assertIsNotNone(resp.id)
        self.assertIn("Random Forest", resp.name)
        self.assertTrue(Path(resp.artifact_path).exists())
        self.assertIn("accuracy", resp.metrics)

    def test_get_model_metrics(self):
        req = ModelTrainRequest(
            dataset_id=self.dataset.id,
            model_type="logistic_regression",
            random_seed=42,
        )
        model_resp = self.service.train_model(req)

        metrics_resp = self.service.get_model_metrics(model_resp.id)
        self.assertEqual(metrics_resp.model_id, model_resp.id)
        self.assertIn("accuracy", metrics_resp.metrics)
        self.assertIsNotNone(metrics_resp.confusion_matrix)
        self.assertIn("matrix", metrics_resp.confusion_matrix)

    def test_list_and_delete_model(self):
        req = ModelTrainRequest(
            dataset_id=self.dataset.id,
            model_type="random_forest",
            hyperparameters={"n_estimators": 10, "max_depth": 3},
            random_seed=42,
        )
        resp = self.service.train_model(req)

        models = self.service.list_models()
        self.assertGreaterEqual(len(models), 1)

        # Delete
        deleted = self.service.delete_model(resp.id)
        self.assertTrue(deleted)

        with self.assertRaises(ModelNotFoundError):
            self.service.get_model(resp.id)

    def test_invalid_dataset_id_raises_not_found(self):
        req = ModelTrainRequest(
            dataset_id="non-existent-id",
            model_type="logistic_regression",
        )
        with self.assertRaises(DatasetNotFoundError):
            self.service.train_model(req)


if __name__ == "__main__":
    unittest.main()
