"""Integration tests for Cryptographic Audit API (/api/v1/audit) and Adversarial Tamper Simulation."""
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
from backend.app.db.models import AuditRecord
from backend.app.db.repositories.dataset_repository import DatasetRepository
from backend.app.main import app
from backend.app.schemas.dataset import DatasetCreate
from backend.app.schemas.model import ModelTrainRequest
from backend.app.schemas.prediction import PredictionRequest
from backend.app.services.prediction_service import PredictionService
from backend.app.services.training_service import TrainingService


class TestAuditAPI(unittest.TestCase):
    def setUp(self):
        # In-memory database with StaticPool so all client calls share the same memory DB
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
        self.csv_filename = "audit_api_flow.csv"
        df.to_csv(self.data_raw_dir / self.csv_filename, index=False)

        # Register dataset & train model
        db = self.SessionLocal()
        repo = DatasetRepository(db)
        dataset = repo.create(
            DatasetCreate(
                name="Audit API Dataset",
                source="api_fixtures",
                file_name=self.csv_filename,
                file_hash="hash_audit_test_123",
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

        # Make 3 predictions to generate 3 chained audit records
        pred_service = PredictionService(db)
        self.predictions = []
        for i in range(3):
            p = pred_service.predict(
                PredictionRequest(
                    model_id=self.model_id,
                    features={"proto": "tcp", "service": "http", "dur": float(i + 0.1), "sbytes": 100 * (i + 1)},
                )
            )
            self.predictions.append(p)

        db.close()

    def tearDown(self):
        app.dependency_overrides.clear()
        settings.DATA_RAW_DIR = self._orig_raw
        settings.MODELS_TRAINED_DIR = self._orig_trained
        settings.MODELS_ARTIFACTS_DIR = self._orig_artifacts
        self.temp_dir.cleanup()

    def test_audit_records_listing_and_inspection(self):
        # 1. List records
        res = self.client.get("/api/v1/audit/records")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 3)
        self.assertEqual(len(data["records"]), 3)

        first_rec = data["records"][0]
        self.assertEqual(first_rec["sequence_number"], 1)

        # 2. Get record by ID
        rec_id = first_rec["id"]
        detail_res = self.client.get(f"/api/v1/audit/records/{rec_id}")
        self.assertEqual(detail_res.status_code, 200)
        self.assertEqual(detail_res.json()["id"], rec_id)

        # 3. Get record by prediction ID
        pred_id = self.predictions[0].prediction_id
        pred_rec_res = self.client.get(f"/api/v1/audit/predictions/{pred_id}")
        self.assertEqual(pred_rec_res.status_code, 200)
        self.assertEqual(pred_rec_res.json()["prediction_id"], pred_id)

    def test_ledger_status(self):
        res = self.client.get("/api/v1/audit/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_records"], 3)
        self.assertEqual(data["latest_sequence"], 3)
        self.assertTrue(data["is_intact"])
        self.assertFalse(data["tamper_detected"])

    def test_verify_intact_chain(self):
        res = self.client.post("/api/v1/audit/verify", json={"verify_entire_chain": True})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["verified"])
        self.assertFalse(data["tamper_detected"])
        self.assertEqual(data["checked_records"], 3)
        self.assertEqual(len(data["failed_records"]), 0)

    def test_adversarial_tamper_detection_simulation(self):
        # Adversarial attack: directly alter payload of record 2 in the database
        db = self.SessionLocal()
        record_2 = db.query(AuditRecord).filter(AuditRecord.sequence_number == 2).first()
        self.assertIsNotNone(record_2)

        # Parse and alter the payload (e.g., flip predicted class from 1 to 0 or alter features)
        payload = json.loads(record_2.payload_json)
        payload["predicted_class"] = "TAMPERED_CLASS"
        record_2.payload_json = json.dumps(payload)
        db.commit()
        db.close()

        # Run verification via API
        res = self.client.post("/api/v1/audit/verify", json={"verify_entire_chain": True})
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Assert tamper detection!
        self.assertFalse(data["verified"])
        self.assertTrue(data["tamper_detected"])
        self.assertGreater(len(data["failed_records"]), 0)

        # Confirm exact sequence number corrupted is identified
        corrupted_seqs = [f["sequence_number"] for f in data["failed_records"]]
        self.assertIn(2, corrupted_seqs)

        # Confirm /status reflects compromise
        status_res = self.client.get("/api/v1/audit/status")
        self.assertEqual(status_res.status_code, 200)
        status_data = status_res.json()
        self.assertTrue(status_data["tamper_detected"])
        self.assertFalse(status_data["is_intact"])


if __name__ == "__main__":
    unittest.main()
