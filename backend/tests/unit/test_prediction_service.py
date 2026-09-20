"""Unit and integration tests for PredictionService, Evidence Packaging, and Hash Chain Anchoring."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings
from backend.app.core.exceptions import ModelNotFoundError
from backend.app.cryptography.canonicalization import canonicalize
from backend.app.cryptography.hash_chain import GENESIS_PREVIOUS_HASH
from backend.app.cryptography.hashing import sha256_hash
from backend.app.cryptography.verifier import verify_ledger
from backend.app.db.database import Base
from backend.app.db.repositories.audit_repository import AuditRepository
from backend.app.db.repositories.dataset_repository import DatasetRepository
from backend.app.schemas.dataset import DatasetCreate
from backend.app.schemas.model import ModelTrainRequest
from backend.app.schemas.prediction import BatchPredictionRequest, PredictionRequest
from backend.app.services.prediction_service import PredictionService
from backend.app.services.training_service import TrainingService


class TestPredictionService(unittest.TestCase):
    def setUp(self):
        # In-memory database with StaticPool for cross-session persistence
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        # Temporary file storage
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

        # Create training CSV
        np.random.seed(42)
        n_rows = 100
        df = pd.DataFrame({
            "proto": np.random.choice(["tcp", "udp"], size=n_rows),
            "service": np.random.choice(["http", "dns"], size=n_rows),
            "dur": np.random.exponential(scale=1.5, size=n_rows),
            "sbytes": np.random.randint(100, 3000, size=n_rows),
            "label": np.random.choice([0, 1], size=n_rows, p=[0.5, 0.5]),
        })
        self.csv_file = "test_train.csv"
        df.to_csv(self.data_raw_dir / self.csv_file, index=False)

        # Register dataset & train model
        d_repo = DatasetRepository(self.db)
        dataset = d_repo.create(
            DatasetCreate(
                name="Prediction Test Dataset",
                source="test",
                file_name=self.csv_file,
                file_hash="hash_pred_test",
                row_count=n_rows,
                feature_count=4,
                target_column="label",
                validation_status="VALID",
                label_distribution=json.dumps({"0": 50, "1": 50}),
            )
        )

        t_service = TrainingService(self.db)
        self.model_resp = t_service.train_model(
            ModelTrainRequest(
                dataset_id=dataset.id,
                model_type="logistic_regression",
                random_seed=42,
            )
        )
        self.model_id = self.model_resp.id

        self.service = PredictionService(self.db)
        self.audit_repo = AuditRepository(self.db)

    def tearDown(self):
        self.db.close()
        settings.DATA_RAW_DIR = self._orig_raw
        settings.MODELS_TRAINED_DIR = self._orig_trained
        settings.MODELS_ARTIFACTS_DIR = self._orig_artifacts
        self.temp_dir.cleanup()

    def test_single_prediction_and_audit_anchoring(self):
        sample = {
            "proto": "tcp",
            "service": "http",
            "dur": 0.5,
            "sbytes": 1200,
        }
        req = PredictionRequest(model_id=self.model_id, features=sample)
        resp = self.service.predict(req)

        self.assertIsNotNone(resp.prediction_id)
        self.assertEqual(resp.model_id, self.model_id)
        self.assertIn(resp.predicted_class, ["0", "1"])
        self.assertIsNotNone(resp.probabilities)
        self.assertGreater(resp.latency_ms, 0.0)

        # Verify input hash is deterministic SHA-256 of canonical JSON
        expected_input_hash = sha256_hash(canonicalize(sample))
        self.assertEqual(resp.input_hash, expected_input_hash)

        # Verify AuditRecord was created and sequentially anchored
        audit_rec = self.audit_repo.get_by_prediction_id(resp.prediction_id)
        self.assertIsNotNone(audit_rec)
        self.assertEqual(audit_rec.sequence_number, 1)
        self.assertEqual(audit_rec.previous_hash, GENESIS_PREVIOUS_HASH)

        # Verify payload contains canonical inference evidence
        payload = json.loads(audit_rec.payload_json)
        self.assertEqual(payload["event_type"], "INFERENCE")
        self.assertEqual(payload["input_hash"], expected_input_hash)
        self.assertEqual(payload["model_id"], self.model_id)
        self.assertEqual(payload["prediction_id"], resp.prediction_id)

    def test_batch_prediction_sequential_hash_chain(self):
        samples = [
            {"proto": "tcp", "service": "http", "dur": 0.1, "sbytes": 500},
            {"proto": "udp", "service": "dns", "dur": 0.05, "sbytes": 120},
            {"proto": "tcp", "service": "http", "dur": 2.5, "sbytes": 4500},
        ]
        req = BatchPredictionRequest(model_id=self.model_id, samples=samples)
        batch_resp = self.service.predict_batch(req)

        self.assertEqual(batch_resp.total_samples, 3)
        self.assertEqual(len(batch_resp.predictions), 3)
        self.assertGreater(batch_resp.processing_time_ms, 0.0)

        # Verify audit chain records
        chain = self.audit_repo.get_chain()
        self.assertEqual(len(chain), 3)

        # Record 1
        self.assertEqual(chain[0].sequence_number, 1)
        self.assertEqual(chain[0].previous_hash, GENESIS_PREVIOUS_HASH)

        # Record 2 links to Record 1
        self.assertEqual(chain[1].sequence_number, 2)
        self.assertEqual(chain[1].previous_hash, chain[0].record_hash)

        # Record 3 links to Record 2
        self.assertEqual(chain[2].sequence_number, 3)
        self.assertEqual(chain[2].previous_hash, chain[1].record_hash)

        # Verify entire chain with independent cryptographic verifier
        v_res = verify_ledger(chain)
        self.assertTrue(v_res.verified)
        self.assertEqual(v_res.checked_count, 3)
        self.assertEqual(len(v_res.failed_records), 0)

    def test_get_and_list_predictions(self):
        sample = {"proto": "tcp", "service": "http", "dur": 0.3, "sbytes": 800}
        pred = self.service.predict(PredictionRequest(model_id=self.model_id, features=sample))

        fetched = self.service.get_prediction(pred.prediction_id)
        self.assertEqual(fetched.prediction_id, pred.prediction_id)
        self.assertEqual(fetched.input_hash, pred.input_hash)

        listing = self.service.list_predictions()
        self.assertGreaterEqual(listing["total"], 1)
        self.assertEqual(len(listing["predictions"]), 1)

    def test_nonexistent_model_raises_error(self):
        sample = {"proto": "tcp", "service": "http", "dur": 0.3, "sbytes": 800}
        with self.assertRaises(ModelNotFoundError):
            self.service.predict(PredictionRequest(model_id="invalid-id-xyz", features=sample))


if __name__ == "__main__":
    unittest.main()
