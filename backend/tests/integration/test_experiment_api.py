"""Integration tests for Experiment API endpoints (/api/v1/experiments)."""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_list_experiments_endpoint(client):
    response = client.get("/api/v1/experiments")
    assert response.status_code == 200
    data = response.json()
    assert "experiments" in data
    assert data["total"] == 4
    ids = [e["experiment_id"] for e in data["experiments"]]
    assert "EXP-A" in ids
    assert "EXP-B" in ids
    assert "EXP-C" in ids
    assert "EXP-D" in ids

def test_get_experiment_endpoint(client):
    response = client.get("/api/v1/experiments/EXP-A")
    assert response.status_code == 200
    data = response.json()
    assert data["experiment_id"] == "EXP-A"
    assert "metrics" in data

def test_run_experiment_endpoint(client):
    response = client.post("/api/v1/experiments/EXP-D/run", json={"n_samples": 400})
    assert response.status_code == 200
    data = response.json()
    assert data["experiment_id"] == "EXP-D"
    assert data["status"] == "COMPLETED"
    assert "comparison" in data

def test_invalid_experiment_id(client):
    response = client.get("/api/v1/experiments/EXP-UNKNOWN")
    assert response.status_code == 400

def test_export_evidence_endpoint(client):
    response = client.post("/api/v1/experiments/EXP-C/evidence", json={"n_blocks": 12, "random_state": 42})

    assert response.status_code == 200
    data = response.json()
    assert data["experiment_id"] == "EXP-C"
    assert len(data["package_hash"]) == 64
    assert "experiment.json" in data["files"]
    assert "reproducibility-manifest.json" in data["files"]

def test_presentation_summary_endpoint_is_not_treated_as_experiment_id(client):
    response = client.get("/api/v1/experiments/presentation-summary")

    assert response.status_code == 200
    data = response.json()
    assert "research_question" in data
    assert "experiments" in data
    assert len(data["experiments"]) == 4


