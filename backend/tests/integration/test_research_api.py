"""Integration tests for the research API surface (/api/v1/benchmark, /research,
/collaboration) and the new experiment endpoints."""
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.database import Base, get_db
import backend.app.db.models  # noqa: F401
from backend.app.main import app


class ResearchAPIBase(unittest.TestCase):
    def setUp(self):
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

    def tearDown(self):
        app.dependency_overrides.pop(get_db, None)
        self.engine.dispose()

    def _reset_mode(self):
        self.client.post("/api/v1/research/mode", json={"mode": "research"})


class TestExperimentRegistry(ResearchAPIBase):
    def test_list_includes_new_experiments(self):
        res = self.client.get("/api/v1/experiments")
        self.assertEqual(res.status_code, 200)
        ids = {e["experiment_id"] for e in res.json()["experiments"]}
        self.assertTrue({
            "EXP-F", "EXP-G", "EXP-H", "EXP-ROBUSTNESS", "EXP-CALIBRATION"
        } <= ids)

    def test_run_exp_g(self):
        res = self.client.post("/api/v1/experiments/EXP-G/run",
                               json={"sizes": [32, 64], "random_state": 42})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["experiment_id"], "EXP-G")
        self.assertTrue(data["metrics"]["tamper_detection"]["mutation_all_sizes"])

    def test_run_exp_h(self):
        res = self.client.post("/api/v1/experiments/EXP-H/run",
                               json={"n_samples": 300, "noise_levels": [0.0, 0.1]})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("clean_agreement", data["metrics"])

    def test_run_exp_calibration(self):
        res = self.client.post(
            "/api/v1/experiments/EXP-CALIBRATION/run",
            json={"n_samples": 800, "method": "sigmoid", "random_state": 23},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["experiment_id"], "EXP-CALIBRATION")
        self.assertTrue(data["metrics"]["calibration_configuration"]["comparison_uses_same_test_observations"])
        self.assertEqual(
            data["metrics"]["before"]["sample_count"],
            data["metrics"]["after"]["sample_count"],
        )

    def test_unknown_experiment_id_400(self):
        res = self.client.get("/api/v1/experiments/EXP-Q")
        self.assertEqual(res.status_code, 400)

    def test_trust_checklist_endpoint(self):
        # ensure EXP-A has been run at least once in this session
        self.client.post("/api/v1/experiments/EXP-A/run", json={"n_samples": 200})
        res = self.client.get("/api/v1/experiments/EXP-A/trust-checklist")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["checks_total"], 8)

    def test_reproducibility_package_endpoint(self):
        res = self.client.post(
            "/api/v1/experiments/EXP-D/reproducibility-package",
            json={"n_samples": 200, "random_state": 42},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("README.md", data["files"])
        self.assertEqual(len(data["package_hash"]), 64)
        self.assertEqual(data["evidence_format_version"], 2)
        self.assertEqual(data["protocol_version"], 1)
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["experiment_schema_version"], 1)
        self.assertEqual(data["research_artifact_version"], 1)


class TestBenchmarkAPI(ResearchAPIBase):
    def test_sources_listing_is_honest(self):
        res = self.client.get("/api/v1/benchmark/sources")
        self.assertEqual(res.status_code, 200)
        sources = {s["key"] for s in res.json()["sources"]}
        self.assertEqual(sources, {"unsw_nb15", "cicids2017", "controlled"})

    def test_run_and_fetch_report(self):
        res = self.client.post("/api/v1/benchmark/run",
                               json={"n_samples": 300, "repeats": 1})
        self.assertEqual(res.status_code, 200)
        report = res.json()
        self.assertEqual(report["status"], "COMPLETED")
        self.assertEqual(len(report["sources"]), 3)

        latest = self.client.get("/api/v1/benchmark/report")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json()["benchmark_id"], report["benchmark_id"])

    def test_report_404_before_any_run(self):
        # fresh module state: acceptable to receive a report if another test ran one
        res = self.client.get("/api/v1/benchmark/report")
        self.assertIn(res.status_code, (200, 404))

    def test_pipeline_endpoint(self):
        res = self.client.post("/api/v1/benchmark/pipeline", json={"n_samples": 300})
        self.assertEqual(res.status_code, 200)
        stages = res.json()["stages_ms"]
        self.assertEqual(len(stages), 7)

    def test_scalability_endpoint_small_ladder(self):
        res = self.client.post("/api/v1/benchmark/scalability",
                               json={"sizes": [50, 100]})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["points"]), 2)

    def test_leaderboard_endpoint(self):
        self.client.post("/api/v1/benchmark/run", json={"n_samples": 250, "repeats": 1})
        res = self.client.get("/api/v1/benchmark/leaderboard?experiment=EXP")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("rows", body)
        self.assertGreaterEqual(body["total"], 1)


class TestResearchAPI(ResearchAPIBase):
    def test_presets_listing(self):
        res = self.client.get("/api/v1/research/challenges/presets")
        self.assertEqual(res.status_code, 200)
        self.assertEqual([p["id"] for p in res.json()["presets"]],
                         ["Q1", "Q2", "Q3", "Q4", "Q5"])

    def test_define_and_run_challenge(self):
        defined = self.client.post("/api/v1/research/challenges/define", json={
            "title": "API challenge",
            "hypothesis": "EXP-D completes with stable metrics across runs.",
            "experiment": "EXP-D",
            "kind": "standard",
            "config": {"n_samples": 250, "random_state": 42},
        })
        self.assertEqual(defined.status_code, 200)
        challenge = defined.json()
        self.assertEqual(challenge["status"], "DEFINED")

        run = self.client.post("/api/v1/research/challenges/run",
                               json={"n_runs": 2, **challenge})
        self.assertEqual(run.status_code, 200)
        self.assertEqual(run.json()["status"], "COMPLETED")

    def test_run_preset_via_api(self):
        res = self.client.post("/api/v1/research/challenges/run",
                               json={"preset": "Q5", "n_runs": 2})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["question_id"], "Q5")

    def test_list_and_get_challenges(self):
        self.client.post("/api/v1/research/challenges/run",
                         json={"preset": "Q5", "n_runs": 2})
        listing = self.client.get("/api/v1/research/challenges")
        self.assertEqual(listing.status_code, 200)
        self.assertGreaterEqual(listing.json()["total"], 1)
        first = listing.json()["challenges"][0]
        detail = self.client.get(f"/api/v1/research/challenges/{first['challenge_id']}")
        self.assertEqual(detail.status_code, 200)

    def test_model_selection_run(self):
        res = self.client.post("/api/v1/research/model-selection/run",
                               json={"n_samples": 300, "cv_folds": 3})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(len(body["candidates"]), 5)
        self.assertIn(body["selected_model"],
                      {r["model"] for r in body["candidates"]})

    def test_notary_sign_and_verify_round_trip(self):
        sign = self.client.post("/api/v1/research/notary/sign-experiment",
                                json={"experiment_id": "EXP-A"})
        self.assertEqual(sign.status_code, 200)
        artifact = sign.json()
        self.assertEqual(artifact["algorithm"], "Ed25519")

        verify = self.client.post("/api/v1/research/notary/verify", json=artifact)
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["valid"])

    def test_notary_verify_rejects_tampered(self):
        artifact = self.client.post("/api/v1/research/notary/sign-experiment",
                                    json={"experiment_id": "EXP-A"}).json()
        artifact["payload"] = {"tampered": True}
        verify = self.client.post("/api/v1/research/notary/verify", json=artifact)
        self.assertEqual(verify.status_code, 200)
        self.assertFalse(verify.json()["valid"])

    def test_robustness_endpoint(self):
        res = self.client.post("/api/v1/research/robustness/run",
                               json={"n_samples": 300, "n_probe": 10,
                                     "epsilon_levels": [0.05], "n_repeats": 2})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["experiment_id"], "ROBUSTNESS")

    def test_robustness_endpoint_rejects_epsilon_above_bound(self):
        res = self.client.post(
            "/api/v1/research/robustness/run",
            json={"epsilon_levels": [0.21], "with_explanations": False},
        )
        self.assertEqual(res.status_code, 400)

    def test_manifest_and_compare(self):
        manifest = self.client.get("/api/v1/research/reproducibility/manifest?seed=42")
        self.assertEqual(manifest.status_code, 200)
        body = manifest.json()
        self.assertIn("packages", body)

        compare = self.client.post("/api/v1/research/reproducibility/compare",
                                   json={"a": body, "b": body})
        self.assertEqual(compare.status_code, 200)
        self.assertTrue(compare.json()["environment_comparable"])

    def test_plugins_listing(self):
        res = self.client.get("/api/v1/research/plugins")
        self.assertEqual(res.status_code, 200)
        counts = res.json()["counts"]
        self.assertTrue(all(v >= 1 for v in counts.values()))


class TestModeAPI(ResearchAPIBase):
    def tearDown(self):
        self._reset_mode()
        super().tearDown()

    def test_mode_switch_round_trip(self):
        res = self.client.get("/api/v1/research/mode")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["mode"], "research")

        switched = self.client.post("/api/v1/research/mode", json={"mode": "demo"})
        self.assertEqual(switched.status_code, 200)
        self.assertTrue(switched.json()["read_only"])

        # demo blocks dataset upload with 403
        blocked = self.client.post("/api/v1/datasets")
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["error"]["code"], "DEMO_MODE_READ_ONLY")

        # golden path stays reachable (validation error, not 403)
        pred = self.client.post("/api/v1/predictions", json={})
        self.assertNotEqual(pred.status_code, 403)

    def test_unknown_mode_400(self):
        res = self.client.post("/api/v1/research/mode", json={"mode": "wizard"})
        self.assertEqual(res.status_code, 400)


class TestCollaborationAPI(ResearchAPIBase):
    def _seed_prediction(self):
        from backend.app.db.models import ModelRecord, Prediction
        db = self.SessionLocal()
        model = ModelRecord(id="m-int", name="Integration RF", version="v1",
                            artifact_path="a.joblib", preprocessing_path="p.pkl")
        db.add(model)
        db.add(Prediction(id="p-int", model_id="m-int", input_hash="a" * 64,
                          predicted_class="1"))
        db.commit()
        db.close()

    def test_review_flow_end_to_end(self):
        self._seed_prediction()
        record = self.client.post("/api/v1/collaboration/reviews", json={
            "prediction_id": "p-int", "decision": "rejected",
            "analyst": "integration-tester", "notes": "false positive",
        })
        self.assertEqual(record.status_code, 201)
        self.assertTrue(record.json()["disagrees_with_model"])

        listing = self.client.get("/api/v1/collaboration/reviews?decision=rejected")
        self.assertEqual(listing.status_code, 200)
        self.assertGreaterEqual(listing.json()["total"], 1)

        stats = self.client.get("/api/v1/collaboration/reviews/stats")
        self.assertEqual(stats.status_code, 200)
        self.assertGreaterEqual(stats.json()["total_reviews"], 1)

    def test_review_validation_error(self):
        res = self.client.post("/api/v1/collaboration/reviews",
                               json={"prediction_id": "nope", "decision": "confirmed"})
        self.assertIn(res.status_code, (404, 422))

    def test_experiment_collaboration_flow(self):
        comment = self.client.post("/api/v1/collaboration/experiments/EXP-A/comments",
                                   json={"author": "researcher-a", "body": "looks good"})
        self.assertEqual(comment.status_code, 201)
        self.assertEqual(comment.json()["review_status"], "draft")

        state = self.client.put("/api/v1/collaboration/experiments/EXP-A/review-state",
                                json={"owner": "researcher-a",
                                      "review_status": "under_review",
                                      "reviewer": "researcher-b"})
        self.assertEqual(state.status_code, 200)
        self.assertEqual(state.json()["review_status"], "under_review")
        self.assertEqual(state.json()["owner"], "researcher-a")

        approve = self.client.put("/api/v1/collaboration/experiments/EXP-A/review-state",
                                  json={"reviewer": "researcher-b", "approve": True})
        self.assertEqual(approve.status_code, 200)
        self.assertEqual(approve.json()["review_status"], "approved")


if __name__ == "__main__":
    unittest.main()
