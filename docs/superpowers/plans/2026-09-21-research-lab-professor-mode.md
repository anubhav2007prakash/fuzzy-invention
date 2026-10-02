# Research Lab and Professor Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Research Lab v1 and Professor Mode as sequential, evidence-backed enhancements for SentinelCrypt AI.

**Architecture:** Extend the existing `ExperimentService` instead of adding a parallel research subsystem. The backend will enrich existing EXP-A through EXP-D results with reproducibility manifests, canonical hashes, trust-profile dimensions, evidence-package export, and presentation summaries; the frontend will consume those enriched APIs through the existing React/Vite dashboard patterns.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy session injection, pytest, scikit-learn, SHAP, SHA-256 canonical JSON utilities, React 18, Vite, lucide-react.

## Global Constraints

- Do not fabricate research results; every numerical metric shown in the UI must come from an actual experiment run, stored metadata, deterministic configuration, or clearly labeled static project context.
- Preserve existing endpoints: `GET /api/v1/experiments`, `GET /api/v1/experiments/{exp_id}`, and `POST /api/v1/experiments/{exp_id}/run`.
- Define fixed literal experiment routes before dynamic `/{exp_id}` routes so `presentation-summary` is never treated as an experiment id.
- Current EXP-A through EXP-D results use synthetic data and must remain labeled as synthetic where relevant.
- The audit ledger is tamper-evident, not tamper-proof, and must not be described as a blockchain.
- Demo mode must not mutate real audit ledger records.
- Use existing frontend primitives: `card`, `table`, `badge`, `btn`, `Alert`, `StatusBadge`, and lucide-react icons.
- Keep implementation scoped to Research Lab v1 and Professor Mode; do not implement statistical significance tests, OOD detection, unknown attack mode, AI assistant, asymmetric signatures, or ZIP archive generation.

---

## File Structure

Modify these backend files:

- `backend/app/services/experiment_service.py`: add configuration validation, research envelope enrichment, canonical hashes, trust profiles, evidence export, and presentation summary helpers.
- `backend/app/api/v1/experiments.py`: add `presentation-summary` and `evidence` endpoints while preserving existing list/get/run behavior.
- `backend/tests/unit/test_experiments.py`: add service-level tests for envelopes, hashes, trust profiles, evidence export, and summary data.
- `backend/tests/integration/test_experiment_api.py`: add API tests for new endpoints and route ordering.

Modify these frontend files:

- `frontend/src/api/experiments.js`: add `exportEvidence` and `presentationSummary` client methods.
- `frontend/src/pages/Experiments.jsx`: refactor the current experiments page into Research Lab v1 while keeping the `/experiments` route.
- `frontend/src/App.jsx`: add Professor Mode route.
- `frontend/src/components/layout/Sidebar.jsx`: rename Experiments to Research Lab and add Professor Mode navigation.

Create these frontend files:

- `frontend/src/components/research/TrustProfileBars.jsx`: render measurable trust dimensions.
- `frontend/src/components/research/ReproducibilityPanel.jsx`: render manifest and hash metadata.
- `frontend/src/pages/ProfessorMode.jsx`: render presentation and controlled EXP-C demo view.

Do not move existing result artifacts. New evidence packages are written under `results/evidence/<experiment-id>/`.

---

### Task 1: Backend Research Envelope, Validation, Hashes, and Trust Profile

**Files:**
- Modify: `backend/app/services/experiment_service.py`
- Test: `backend/tests/unit/test_experiments.py`

**Interfaces:**
- Produces: `ExperimentService.validate_experiment_config(exp_id: str, config: Optional[Dict[str, Any]]) -> Dict[str, Any]`
- Produces: `ExperimentService.enrich_research_result(result: Dict[str, Any], config: Optional[Dict[str, Any]]) -> Dict[str, Any]`
- Produces: `ExperimentService.calculate_result_hash(result: Dict[str, Any]) -> str`
- Produces: `ExperimentService.calculate_configuration_hash(exp_id: str, config: Dict[str, Any]) -> str`
- Produces: `ExperimentService.build_run_manifest(result: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]`
- Produces: `ExperimentService.build_trust_profile(result: Dict[str, Any]) -> List[Dict[str, Any]]`
- Produces: `ExperimentService.get_git_metadata() -> Dict[str, Any]`
- Consumes: existing `canonicalize(payload: dict) -> str` and `sha256_hash(data: str | bytes) -> str`

- [ ] **Step 1: Add failing service tests for the research envelope**

Append these tests to `backend/tests/unit/test_experiments.py`:

```python
def test_research_envelope_is_added_to_experiment_result(service):
    res = service.run_exp_a({"n_samples": 300, "random_state": 42})

    assert res["experiment_id"] == "EXP-A"
    assert res["status"] == "COMPLETED"
    assert len(res["result_hash"]) == 64
    assert len(res["configuration_hash"]) == 64
    assert res["run_manifest"]["experiment_id"] == "EXP-A"
    assert res["run_manifest"]["configuration"]["n_samples"] == 300
    assert res["run_manifest"]["configuration"]["random_state"] == 42
    assert res["run_manifest"]["dataset_scope"] == "synthetic"
    assert res["evidence_package"]["status"] == "not_exported"
    assert {d["label"] for d in res["trust_profile"]} == {
        "Detection",
        "Explanation Stability",
        "Evidence Integrity",
        "Reproducibility",
        "Data Quality",
    }


def test_hash_helpers_are_deterministic_for_same_payload(service):
    payload = {
        "experiment_id": "EXP-Z",
        "status": "COMPLETED",
        "metrics": {"f1_score": 0.9123456},
        "timestamp": "2026-09-21T00:00:00Z",
    }
    config = {"n_samples": 300, "random_state": 42}

    assert service.calculate_result_hash(payload) == service.calculate_result_hash(dict(payload))
    assert service.calculate_configuration_hash("EXP-Z", config) == service.calculate_configuration_hash("exp-z", dict(config))


def test_validate_experiment_config_rejects_invalid_values(service):
    with pytest.raises(ValueError, match="n_samples"):
        service.validate_experiment_config("EXP-A", {"n_samples": 0, "random_state": 42})

    with pytest.raises(ValueError, match="noise_levels"):
        service.validate_experiment_config("EXP-B", {"noise_levels": [-0.1], "n_repetitions": 3, "random_state": 42})

    with pytest.raises(ValueError, match="n_blocks"):
        service.validate_experiment_config("EXP-C", {"n_blocks": "many", "random_state": 42})


def test_data_quality_trust_dimension_is_not_evaluated_without_real_dataset(service):
    res = service.run_exp_d({"n_samples": 400, "random_state": 42})
    data_quality = next(d for d in res["trust_profile"] if d["label"] == "Data Quality")

    assert data_quality["status"] == "not_evaluated"
    assert data_quality["value"] is None
    assert "No real dataset health report" in data_quality["explanation"]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
pytest backend/tests/unit/test_experiments.py::test_research_envelope_is_added_to_experiment_result backend/tests/unit/test_experiments.py::test_hash_helpers_are_deterministic_for_same_payload backend/tests/unit/test_experiments.py::test_validate_experiment_config_rejects_invalid_values backend/tests/unit/test_experiments.py::test_data_quality_trust_dimension_is_not_evaluated_without_real_dataset -v
```

Expected: FAIL because the new methods and enriched fields do not exist yet.

- [ ] **Step 3: Add constants and helper imports**

Modify the import block in `backend/app/services/experiment_service.py`:

```python
import subprocess
from copy import deepcopy
```

Add these constants below `RESULTS_DIR.mkdir(...)`:

```python
EXPERIMENT_RESULT_FILES = {
    "EXP-A": "exp_a_cross_dataset.json",
    "EXP-B": "exp_b_xai_stability.json",
    "EXP-C": "exp_c_ledger_integrity.json",
    "EXP-D": "exp_d_model_comparison.json",
}

RESEARCH_ENVELOPE_KEYS = {
    "run_manifest",
    "result_hash",
    "configuration_hash",
    "trust_profile",
    "evidence_package",
}

SYNTHETIC_DATA_DISCLAIMER = (
    "Current benchmark results use deterministic synthetic network-flow data with controlled properties. "
    "They are not real UNSW-NB15 or CICIDS2017 measurements."
)
```

- [ ] **Step 4: Add validation and hashing helpers**

Add these methods inside `ExperimentService` before `run_exp_a`:

```python
    @staticmethod
    def _positive_int(value: Any, field_name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be a positive integer.")
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be a positive integer.") from None
        if parsed <= 0:
            raise ValueError(f"{field_name} must be a positive integer.")
        return parsed

    @staticmethod
    def _integer(value: Any, field_name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be an integer.")
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be an integer.") from None

    @staticmethod
    def _positive_float_list(value: Any, field_name: str) -> List[float]:
        if not isinstance(value, list) or not value:
            raise ValueError(f"{field_name} must be a non-empty list of positive numbers.")
        parsed: List[float] = []
        for item in value:
            try:
                number = float(item)
            except (TypeError, ValueError):
                raise ValueError(f"{field_name} must contain only positive numbers.") from None
            if not np.isfinite(number) or number <= 0:
                raise ValueError(f"{field_name} must contain only positive numbers.")
            parsed.append(number)
        return parsed

    def validate_experiment_config(self, exp_id: str, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        normalized_id = exp_id.upper().strip()
        raw = config or {}

        if normalized_id == "EXP-A":
            return {
                "n_samples": self._positive_int(raw.get("n_samples", 1200), "n_samples"),
                "random_state": self._integer(raw.get("random_state", 42), "random_state"),
            }
        if normalized_id == "EXP-B":
            return {
                "noise_levels": self._positive_float_list(raw.get("noise_levels", [0.01, 0.05, 0.10, 0.20]), "noise_levels"),
                "n_repetitions": self._positive_int(raw.get("n_repetitions", 8), "n_repetitions"),
                "random_state": self._integer(raw.get("random_state", 42), "random_state"),
            }
        if normalized_id == "EXP-C":
            return {
                "n_blocks": self._positive_int(raw.get("n_blocks", 50), "n_blocks"),
                "random_state": self._integer(raw.get("random_state", 42), "random_state"),
            }
        if normalized_id == "EXP-D":
            return {
                "n_samples": self._positive_int(raw.get("n_samples", 1500), "n_samples"),
                "random_state": self._integer(raw.get("random_state", 42), "random_state"),
            }
        raise ValueError(f"Unknown experiment ID '{exp_id}'. Must be EXP-A, EXP-B, EXP-C, or EXP-D.")

    @staticmethod
    def _strip_research_envelope(result: Dict[str, Any]) -> Dict[str, Any]:
        return {key: deepcopy(value) for key, value in result.items() if key not in RESEARCH_ENVELOPE_KEYS}

    def calculate_result_hash(self, result: Dict[str, Any]) -> str:
        return sha256_hash(canonicalize(self._strip_research_envelope(result)))

    def calculate_configuration_hash(self, exp_id: str, config: Dict[str, Any]) -> str:
        payload = {"experiment_id": exp_id.upper().strip(), "configuration": config}
        return sha256_hash(canonicalize(payload))
```

- [ ] **Step 5: Add manifest, git metadata, trust profile, and envelope helpers**

Add these methods below the helpers from Step 4:

```python
    def get_git_metadata(self) -> Dict[str, Any]:
        repo_root = Path(__file__).resolve().parents[3]

        def run_git(args: List[str]) -> str:
            return subprocess.check_output(
                ["git", *args],
                cwd=repo_root,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=2,
            ).strip()

        try:
            status = run_git(["status", "--short"])
            return {
                "commit": run_git(["rev-parse", "--short", "HEAD"]),
                "branch": run_git(["rev-parse", "--abbrev-ref", "HEAD"]),
                "dirty_worktree": bool(status),
            }
        except Exception:
            return {"commit": "unknown", "branch": "unknown", "dirty_worktree": None}

    def build_run_manifest(self, result: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        exp_id = result["experiment_id"]
        reproducibility = result.get("reproducibility") or _reproducibility_metadata()
        return {
            "experiment_id": exp_id,
            "title": result.get("title"),
            "status": result.get("status"),
            "configuration": config,
            "random_seed": config.get("random_state"),
            "result_artifact": EXPERIMENT_RESULT_FILES.get(exp_id),
            "dataset_scope": "synthetic",
            "dataset_disclaimer": SYNTHETIC_DATA_DISCLAIMER,
            "git": self.get_git_metadata(),
            "environment": {
                "python_version": reproducibility.get("python_version"),
                "platform": reproducibility.get("platform"),
                "numpy_version": reproducibility.get("numpy_version"),
                "pandas_version": reproducibility.get("pandas_version"),
                "sklearn_version": reproducibility.get("sklearn_version"),
                "shap_version": reproducibility.get("shap_version"),
            },
            "generated_at": reproducibility.get("timestamp_utc") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    @staticmethod
    def _dimension(label: str, value: Optional[float], status: str, measurement: str, explanation: str) -> Dict[str, Any]:
        return {
            "label": label,
            "value": None if value is None else round(float(value), 4),
            "status": status,
            "measurement": measurement,
            "explanation": explanation,
        }

    def build_trust_profile(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        metrics = result.get("metrics") or {}
        comparison = result.get("comparison") or {}

        detection_value: Optional[float] = None
        detection_measurement = "No detection metric available for this experiment."
        if "in_distribution" in metrics:
            detection_value = metrics["in_distribution"].get("f1_score")
            detection_measurement = "In-distribution F1 score from EXP-A."
        elif "random_forest" in comparison:
            detection_value = comparison["random_forest"].get("f1_score")
            detection_measurement = "Random Forest F1 score from EXP-D."
        elif "overall_mean_stability" in metrics:
            detection_value = None
            detection_measurement = "EXP-B measures explanation stability, not detection quality."
        elif "clean_chain_valid" in metrics:
            detection_value = None
            detection_measurement = "EXP-C measures ledger integrity, not detection quality."

        stability_value = metrics.get("overall_mean_stability")
        evidence_value = None
        if "clean_chain_valid" in metrics:
            rate_text = str(metrics.get("tamper_detection_rate", "0%")).replace("%", "")
            try:
                evidence_value = float(rate_text) / 100.0 if metrics.get("clean_chain_valid") else 0.0
            except ValueError:
                evidence_value = 0.0

        manifest_ready = bool(result.get("reproducibility")) and bool(result.get("parameters") or comparison)
        reproducibility_value = 1.0 if manifest_ready else 0.75

        return [
            self._dimension("Detection", detection_value, "measured" if detection_value is not None else "not_applicable", detection_measurement, "Detection trust is derived only from available F1 metrics."),
            self._dimension("Explanation Stability", stability_value, "measured" if stability_value is not None else "not_applicable", "Mean cosine SHAP stability from EXP-B when available.", "Explanation stability is measured only for the XAI perturbation experiment."),
            self._dimension("Evidence Integrity", evidence_value, "measured" if evidence_value is not None else "not_applicable", "Clean-chain verification and tamper detection rate from EXP-C when available.", "Evidence integrity uses controlled synthetic ledger tampering, not a production guarantee."),
            self._dimension("Reproducibility", reproducibility_value, "measured", "Manifest completeness, deterministic configuration, environment metadata, and canonical hashes.", "Reproducibility reflects whether the run records enough metadata to rerun and inspect the experiment."),
            self._dimension("Data Quality", None, "not_evaluated", "No real dataset health report is attached to this synthetic benchmark.", "No real dataset health report exists for this run, so data quality is not scored."),
        ]

    def enrich_research_result(self, result: Dict[str, Any], config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        enriched = deepcopy(result)
        exp_id = enriched["experiment_id"]
        normalized_config = self.validate_experiment_config(exp_id, config or enriched.get("parameters") or {})
        enriched["run_manifest"] = self.build_run_manifest(enriched, normalized_config)
        enriched["result_hash"] = self.calculate_result_hash(enriched)
        enriched["configuration_hash"] = self.calculate_configuration_hash(exp_id, normalized_config)
        enriched["trust_profile"] = self.build_trust_profile(enriched)
        enriched["evidence_package"] = {"status": "not_exported"}
        return enriched
```

- [ ] **Step 6: Enrich all experiment results before writing and returning**

In each `run_exp_*` method, directly before `with open(out_file, "w"...`, add:

```python
        result = self.enrich_research_result(result, cfg)
```

For EXP-A, EXP-B, EXP-C, and EXP-D, this line must appear before `json.dump(result, f, indent=2)` and before `return result`.

- [ ] **Step 7: Update result lookup to use the shared filename map and enrich old artifacts**

Replace the local `filename_map` in `get_experiment_by_id` with `EXPERIMENT_RESULT_FILES`.

Inside the `if file_path.exists()` branch, after `data = json.load(f)`, add:

```python
                    if "run_manifest" not in data:
                        return self.enrich_research_result(data, data.get("parameters") or {})
                    return data
```

In `list_experiments`, replace the local file map with:

```python
        exp_meta = [
            {"id": "EXP-A", "title": "Cross-Dataset Generalization Gap"},
            {"id": "EXP-B", "title": "XAI Attribution Stability under Perturbation"},
            {"id": "EXP-C", "title": "Cryptographic Audit Integrity & Tamper Attacks"},
            {"id": "EXP-D", "title": "Model Architecture & Runtime Overhead Comparison"},
        ]
```

Then set:

```python
            file_path = RESULTS_DIR / EXPERIMENT_RESULT_FILES[meta["id"]]
```

- [ ] **Step 8: Run service tests**

Run:

```bash
pytest backend/tests/unit/test_experiments.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit Task 1**

Run:

```bash
git add backend/app/services/experiment_service.py backend/tests/unit/test_experiments.py
git commit -m "feat: add research experiment envelopes"
```

---

### Task 2: Evidence Package Export and API Endpoint

**Files:**
- Modify: `backend/app/services/experiment_service.py`
- Modify: `backend/app/api/v1/experiments.py`
- Test: `backend/tests/unit/test_experiments.py`
- Test: `backend/tests/integration/test_experiment_api.py`

**Interfaces:**
- Consumes: `ExperimentService.enrich_research_result(...)`
- Produces: `ExperimentService.export_evidence_package(exp_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]`
- Produces: `POST /api/v1/experiments/{exp_id}/evidence`

- [ ] **Step 1: Add failing evidence export unit test**

Append to `backend/tests/unit/test_experiments.py`:

```python
def test_export_evidence_package_writes_expected_files(service):
    service.run_exp_c({"n_blocks": 12, "random_state": 42})

    package = service.export_evidence_package("EXP-C")

    assert package["experiment_id"] == "EXP-C"
    assert package["package_hash"]
    assert len(package["package_hash"]) == 64
    assert package["package_path"].endswith("results/evidence/EXP-C")
    assert set(package["files"]) == {
        "README.md",
        "experiment.json",
        "metrics.json",
        "reproducibility-manifest.json",
        "verification-report.json",
    }

    package_dir = Path(package["package_path"])
    assert (package_dir / "experiment.json").exists()
    assert (package_dir / "metrics.json").exists()
    assert (package_dir / "reproducibility-manifest.json").exists()
    assert (package_dir / "verification-report.json").exists()
    assert (package_dir / "README.md").exists()
```

Add imports at the top of the test file:

```python
from pathlib import Path
```

- [ ] **Step 2: Add failing API integration test**

Append to `backend/tests/integration/test_experiment_api.py`:

```python
def test_export_evidence_endpoint(client):
    response = client.post("/api/v1/experiments/EXP-C/evidence", json={"n_blocks": 12, "random_state": 42})

    assert response.status_code == 200
    data = response.json()
    assert data["experiment_id"] == "EXP-C"
    assert len(data["package_hash"]) == 64
    assert "experiment.json" in data["files"]
    assert "reproducibility-manifest.json" in data["files"]
```

- [ ] **Step 3: Run evidence tests to verify they fail**

Run:

```bash
pytest backend/tests/unit/test_experiments.py::test_export_evidence_package_writes_expected_files backend/tests/integration/test_experiment_api.py::test_export_evidence_endpoint -v
```

Expected: FAIL because export method and endpoint do not exist yet.

- [ ] **Step 4: Implement evidence package export helper**

Add `hash_file` to the hashing import in `backend/app/services/experiment_service.py`:

```python
from backend.app.cryptography.hashing import hash_file, sha256_hash
```

Add this method inside `ExperimentService` after `enrich_research_result`:

```python
    def export_evidence_package(self, exp_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        normalized_id = exp_id.upper().strip()
        if normalized_id not in EXPERIMENT_RESULT_FILES:
            raise ValueError(f"Unknown experiment ID '{exp_id}'. Must be EXP-A, EXP-B, EXP-C, or EXP-D.")

        result = self.run_experiment_by_id(normalized_id, config=config) if config else self.get_experiment_by_id(normalized_id)
        if result is None:
            result = self.run_experiment_by_id(normalized_id, config=config)

        package_dir = RESULTS_DIR / "evidence" / normalized_id
        package_dir.mkdir(parents=True, exist_ok=True)

        metrics_payload = result.get("metrics") or result.get("comparison") or {}
        verification_report = {
            "experiment_id": normalized_id,
            "status": result.get("status"),
            "result_hash": result.get("result_hash"),
            "configuration_hash": result.get("configuration_hash"),
            "trust_profile": result.get("trust_profile", []),
            "ledger_scope": "synthetic_controlled_demo" if normalized_id == "EXP-C" else "not_applicable",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        files_to_write = {
            "experiment.json": result,
            "metrics.json": metrics_payload,
            "reproducibility-manifest.json": result.get("run_manifest", {}),
            "verification-report.json": verification_report,
        }

        for filename, payload in files_to_write.items():
            with open(package_dir / filename, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, sort_keys=True)

        readme = (
            f"# SentinelCrypt Evidence Package: {normalized_id}\n\n"
            f"Generated: {verification_report['generated_at']}\n\n"
            "This package contains deterministic research evidence exported from SentinelCrypt AI.\n"
            "Current benchmark experiments use synthetic data unless a manifest states otherwise.\n"
        )
        with open(package_dir / "README.md", "w", encoding="utf-8") as f:
            f.write(readme)

        file_hashes = {}
        for file_path in sorted(package_dir.iterdir(), key=lambda p: p.name):
            if file_path.is_file():
                file_hashes[file_path.name] = hash_file(str(file_path))

        package_hash = sha256_hash(canonicalize({"files": file_hashes}))
        files = sorted(file_hashes.keys())

        response = {
            "experiment_id": normalized_id,
            "package_path": str(package_dir.as_posix()),
            "files": files,
            "file_hashes": file_hashes,
            "package_hash": package_hash,
            "generated_at": verification_report["generated_at"],
        }
        result["evidence_package"] = {
            "status": "exported",
            "package_path": response["package_path"],
            "package_hash": package_hash,
            "generated_at": response["generated_at"],
        }
        return response
```

- [ ] **Step 5: Add API endpoint**

In `backend/app/api/v1/experiments.py`, add this route before `@router.get("/{exp_id}"...)`:

```python
@router.post(
    "/{exp_id}/evidence",
    summary="Export a portable research evidence package",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
)
def export_experiment_evidence(
    exp_id: str,
    config: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Export structured research evidence files for an experiment."""
    service = ExperimentService(db)
    try:
        return service.export_evidence_package(exp_id, config=config)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evidence export failed for experiment '{exp_id}': {str(e)}",
        )
```

- [ ] **Step 6: Run evidence tests**

Run:

```bash
pytest backend/tests/unit/test_experiments.py::test_export_evidence_package_writes_expected_files backend/tests/integration/test_experiment_api.py::test_export_evidence_endpoint -v
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add backend/app/services/experiment_service.py backend/app/api/v1/experiments.py backend/tests/unit/test_experiments.py backend/tests/integration/test_experiment_api.py
git commit -m "feat: export research evidence packages"
```

---

### Task 3: Presentation Summary Backend Endpoint

**Files:**
- Modify: `backend/app/services/experiment_service.py`
- Modify: `backend/app/api/v1/experiments.py`
- Test: `backend/tests/unit/test_experiments.py`
- Test: `backend/tests/integration/test_experiment_api.py`

**Interfaces:**
- Produces: `ExperimentService.build_presentation_summary() -> Dict[str, Any]`
- Produces: `GET /api/v1/experiments/presentation-summary`
- Consumes: `ExperimentService.list_experiments()`

- [ ] **Step 1: Add failing service test for presentation summary**

Append to `backend/tests/unit/test_experiments.py`:

```python
def test_presentation_summary_contains_research_narrative_and_limitations(service):
    summary = service.build_presentation_summary()

    assert summary["research_question"].startswith("How does explanation reliability")
    assert "Random Forest" in summary["models"]
    assert "SHAP" in summary["xai_method"]
    assert "SHA-256" in summary["cryptographic_evidence"]
    assert len(summary["experiments"]) == 4
    assert "Current experiments use synthetic data." in summary["limitations"]
    assert "research prototype" in " ".join(summary["limitations"]).lower()
```

- [ ] **Step 2: Add failing route-order integration test**

Append to `backend/tests/integration/test_experiment_api.py`:

```python
def test_presentation_summary_endpoint_is_not_treated_as_experiment_id(client):
    response = client.get("/api/v1/experiments/presentation-summary")

    assert response.status_code == 200
    data = response.json()
    assert "research_question" in data
    assert "experiments" in data
    assert len(data["experiments"]) == 4
```

- [ ] **Step 3: Run summary tests to verify they fail**

Run:

```bash
pytest backend/tests/unit/test_experiments.py::test_presentation_summary_contains_research_narrative_and_limitations backend/tests/integration/test_experiment_api.py::test_presentation_summary_endpoint_is_not_treated_as_experiment_id -v
```

Expected: FAIL because summary method and endpoint do not exist yet.

- [ ] **Step 4: Implement presentation summary helper**

Add these methods to `ExperimentService` after `export_evidence_package`:

```python
    @staticmethod
    def _experiment_highlight(exp: Dict[str, Any]) -> Dict[str, Any]:
        exp_id = exp.get("experiment_id")
        if exp.get("status") != "COMPLETED":
            return {"experiment_id": exp_id, "status": exp.get("status"), "highlight": "Ready to run"}

        metrics = exp.get("metrics") or {}
        comparison = exp.get("comparison") or {}

        if exp_id == "EXP-A":
            in_f1 = metrics.get("in_distribution", {}).get("f1_score")
            out_f1 = metrics.get("out_of_distribution", {}).get("f1_score")
            return {"experiment_id": exp_id, "status": "COMPLETED", "highlight": f"In-distribution F1 {in_f1}; out-of-distribution F1 {out_f1}"}
        if exp_id == "EXP-B":
            stability = metrics.get("overall_mean_stability")
            return {"experiment_id": exp_id, "status": "COMPLETED", "highlight": f"Mean SHAP stability {stability}"}
        if exp_id == "EXP-C":
            detection = metrics.get("tamper_detection_rate")
            return {"experiment_id": exp_id, "status": "COMPLETED", "highlight": f"Tamper detection rate {detection}"}
        if exp_id == "EXP-D":
            rf_f1 = comparison.get("random_forest", {}).get("f1_score")
            lr_f1 = comparison.get("logistic_regression", {}).get("f1_score")
            return {"experiment_id": exp_id, "status": "COMPLETED", "highlight": f"Random Forest F1 {rf_f1}; Logistic Regression F1 {lr_f1}"}
        return {"experiment_id": exp_id, "status": exp.get("status"), "highlight": "No highlight available"}

    def build_presentation_summary(self) -> Dict[str, Any]:
        experiments = self.list_experiments()
        completed = [exp for exp in experiments if exp.get("status") == "COMPLETED"]

        return {
            "research_question": "How does explanation reliability and cryptographic evidence verification affect the trustworthiness of machine-learning-based network intrusion detection?",
            "methodology": [
                "Validate or generate deterministic network-flow data.",
                "Train leakage-conscious baseline and ensemble ML models.",
                "Evaluate detection metrics and runtime trade-offs.",
                "Generate SHAP explanations and perturbation-based stability measurements.",
                "Canonicalize evidence and anchor records in a SHA-256 forward-linked audit ledger.",
                "Export reproducibility metadata, hashes, and evidence packages for inspection.",
            ],
            "datasets": [
                {"name": "Synthetic SentinelCrypt Flow Benchmark", "status": "implemented", "scope": "Current EXP-A through EXP-D benchmark data."},
                {"name": "UNSW-NB15", "status": "planned", "scope": "Real dataset support requires feature mapping and checksum validation."},
                {"name": "CICIDS2017", "status": "planned", "scope": "Real cross-dataset evaluation requires compatible feature representation."},
            ],
            "models": ["Logistic Regression", "Random Forest"],
            "xai_method": "SHAP explanations with perturbation-based stability analysis.",
            "cryptographic_evidence": "RFC 8785-style canonical JSON, SHA-256 payload hashes, and a forward-linked tamper-evident audit ledger.",
            "experiments": [self._experiment_highlight(exp) for exp in experiments],
            "completed_experiments": len(completed),
            "total_experiments": len(experiments),
            "limitations": [
                "Current experiments use synthetic data.",
                "The audit ledger is tamper-evident, not tamper-proof.",
                "SentinelCrypt AI is a research prototype, not a production IDS.",
            ],
            "future_work": [
                "Real UNSW-NB15 to CICIDS2017 feature mapping.",
                "Statistical significance testing for repeated runs.",
                "Out-of-distribution and unknown attack research modes.",
                "Digitally signed research result publication packages.",
            ],
        }
```

- [ ] **Step 5: Add the fixed presentation route before dynamic routes**

In `backend/app/api/v1/experiments.py`, place this route above `@router.get("/{exp_id}"...)`:

```python
@router.get(
    "/presentation-summary",
    summary="Get professor-mode research presentation summary",
    response_model=Dict[str, Any],
)
def get_presentation_summary(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Aggregate the current research pipeline, latest results, limitations, and future work."""
    service = ExperimentService(db)
    return service.build_presentation_summary()
```

- [ ] **Step 6: Run summary tests**

Run:

```bash
pytest backend/tests/unit/test_experiments.py::test_presentation_summary_contains_research_narrative_and_limitations backend/tests/integration/test_experiment_api.py::test_presentation_summary_endpoint_is_not_treated_as_experiment_id -v
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

Run:

```bash
git add backend/app/services/experiment_service.py backend/app/api/v1/experiments.py backend/tests/unit/test_experiments.py backend/tests/integration/test_experiment_api.py
git commit -m "feat: add professor presentation summary"
```

---

### Task 4: Frontend Research Lab v1

**Files:**
- Modify: `frontend/src/api/experiments.js`
- Modify: `frontend/src/pages/Experiments.jsx`
- Create: `frontend/src/components/research/TrustProfileBars.jsx`
- Create: `frontend/src/components/research/ReproducibilityPanel.jsx`

**Interfaces:**
- Consumes: `experimentsApi.list()`, `experimentsApi.run(expId, config)`, `experimentsApi.exportEvidence(expId, config)`
- Produces: `TrustProfileBars({ dimensions })`
- Produces: `ReproducibilityPanel({ result })`
- Produces: updated `Experiments` page that validates config and renders enriched research results

- [ ] **Step 1: Update API client**

Modify `frontend/src/api/experiments.js` so the exported object includes:

```javascript
  /**
   * Export portable evidence package for an experiment
   */
  exportEvidence: (expId, config = {}) => {
    return fetchApi(`/experiments/${expId}/evidence`, {
      method: 'POST',
      body: config,
    });
  },

  /**
   * Get professor-mode presentation summary
   */
  presentationSummary: () => {
    return fetchApi('/experiments/presentation-summary', { method: 'GET' });
  },
```

- [ ] **Step 2: Create TrustProfileBars component**

Create `frontend/src/components/research/TrustProfileBars.jsx`:

```jsx
import React from 'react';
import { ShieldCheck } from 'lucide-react';
import StatusBadge from '../common/StatusBadge';

function formatValue(value) {
  if (value === null || value === undefined) return 'Not evaluated';
  return `${Math.round(value * 100)}%`;
}

export default function TrustProfileBars({ dimensions = [] }) {
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">
            <ShieldCheck size={16} style={{ color: 'var(--cyan-neon)' }} />
            Model Trust Profile
          </div>
          <div className="card-subtitle">Dimension-based measurements from stored experiment evidence</div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {dimensions.map((dimension) => {
          const percent = dimension.value === null || dimension.value === undefined
            ? 0
            : Math.max(0, Math.min(100, Math.round(dimension.value * 100)));

          return (
            <div key={dimension.label}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', marginBottom: '6px' }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.84rem', color: 'var(--text-primary)' }}>
                    {dimension.label}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    {dimension.measurement}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="font-mono" style={{ fontSize: '0.8rem', color: 'var(--cyan-neon)' }}>
                    {formatValue(dimension.value)}
                  </span>
                  <StatusBadge status={dimension.status === 'measured' ? 'success' : 'pending'} label={dimension.status} />
                </div>
              </div>
              <div style={{ height: '8px', background: 'var(--bg-input)', borderRadius: '999px', overflow: 'hidden', border: '1px solid var(--border-subtle)' }}>
                <div style={{ width: `${percent}%`, height: '100%', background: 'linear-gradient(90deg, var(--cyan-neon), var(--status-benign))' }} />
              </div>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
                {dimension.explanation}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create ReproducibilityPanel component**

Create `frontend/src/components/research/ReproducibilityPanel.jsx`:

```jsx
import React from 'react';
import { Fingerprint } from 'lucide-react';

function Row({ label, value }) {
  return (
    <tr>
      <td>{label}</td>
      <td className="font-mono" style={{ wordBreak: 'break-all' }}>{value ?? 'unknown'}</td>
    </tr>
  );
}

export default function ReproducibilityPanel({ result }) {
  const manifest = result?.run_manifest || {};
  const environment = manifest.environment || {};
  const git = manifest.git || {};

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">
            <Fingerprint size={16} style={{ color: 'var(--cyan-neon)' }} />
            Reproducibility Manifest
          </div>
          <div className="card-subtitle">Configuration, environment, code version, and canonical hashes</div>
        </div>
      </div>

      <div className="table-container">
        <table className="table">
          <tbody>
            <Row label="Result Hash" value={result?.result_hash} />
            <Row label="Configuration Hash" value={result?.configuration_hash} />
            <Row label="Seed" value={manifest.random_seed} />
            <Row label="Result Artifact" value={manifest.result_artifact} />
            <Row label="Dataset Scope" value={manifest.dataset_scope} />
            <Row label="Git Commit" value={git.commit} />
            <Row label="Git Branch" value={git.branch} />
            <Row label="Dirty Worktree" value={String(git.dirty_worktree)} />
            <Row label="Python" value={environment.python_version} />
            <Row label="Platform" value={environment.platform} />
            <Row label="NumPy" value={environment.numpy_version} />
            <Row label="pandas" value={environment.pandas_version} />
            <Row label="scikit-learn" value={environment.sklearn_version} />
            <Row label="SHAP" value={environment.shap_version} />
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Replace the Experiments page header and metadata**

Modify `frontend/src/pages/Experiments.jsx` imports:

```javascript
import React, { useState, useEffect } from 'react';
import { FlaskConical, Play, Download, RefreshCw, BarChart2, Settings2, PackageCheck } from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';
import Alert from '../components/common/Alert';
import TrustProfileBars from '../components/research/TrustProfileBars';
import ReproducibilityPanel from '../components/research/ReproducibilityPanel';
import { experimentsApi } from '../api/experiments';
```

Use the existing `EXPERIMENTS_META`, but change page copy from `Research Experiments & Benchmark Suite` to `Research Lab`.

- [ ] **Step 5: Add configuration state and validation helpers**

Inside `Experiments.jsx`, above the component:

```javascript
const DEFAULT_CONFIGS = {
  'EXP-A': { n_samples: 1200, random_state: 42 },
  'EXP-B': { noise_levels: '0.01, 0.05, 0.10, 0.20', n_repetitions: 8, random_state: 42 },
  'EXP-C': { n_blocks: 50, random_state: 42 },
  'EXP-D': { n_samples: 1500, random_state: 42 },
};

function parsePositiveInteger(value, label) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isInteger(parsed) || parsed <= 0) return `${label} must be a positive integer.`;
  return null;
}

function parseInteger(value, label) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isInteger(parsed)) return `${label} must be an integer.`;
  return null;
}

function buildConfig(expId, form) {
  const errors = [];
  const config = {};

  if (expId === 'EXP-A' || expId === 'EXP-D') {
    const sampleError = parsePositiveInteger(form.n_samples, 'Sample count');
    const seedError = parseInteger(form.random_state, 'Seed');
    if (sampleError) errors.push(sampleError);
    if (seedError) errors.push(seedError);
    config.n_samples = Number.parseInt(form.n_samples, 10);
    config.random_state = Number.parseInt(form.random_state, 10);
  }

  if (expId === 'EXP-B') {
    const levels = String(form.noise_levels)
      .split(',')
      .map((value) => Number.parseFloat(value.trim()))
      .filter((value) => !Number.isNaN(value));
    if (!levels.length || levels.some((value) => value <= 0)) errors.push('Noise levels must be positive numbers separated by commas.');
    const repetitionError = parsePositiveInteger(form.n_repetitions, 'Repetitions');
    const seedError = parseInteger(form.random_state, 'Seed');
    if (repetitionError) errors.push(repetitionError);
    if (seedError) errors.push(seedError);
    config.noise_levels = levels;
    config.n_repetitions = Number.parseInt(form.n_repetitions, 10);
    config.random_state = Number.parseInt(form.random_state, 10);
  }

  if (expId === 'EXP-C') {
    const blockError = parsePositiveInteger(form.n_blocks, 'Ledger blocks');
    const seedError = parseInteger(form.random_state, 'Seed');
    if (blockError) errors.push(blockError);
    if (seedError) errors.push(seedError);
    config.n_blocks = Number.parseInt(form.n_blocks, 10);
    config.random_state = Number.parseInt(form.random_state, 10);
  }

  return { config, errors };
}
```

Inside the component, add:

```javascript
  const [configForms, setConfigForms] = useState(DEFAULT_CONFIGS);
  const [validationErrors, setValidationErrors] = useState([]);
  const [evidenceExport, setEvidenceExport] = useState(null);
```

- [ ] **Step 6: Update run and export handlers**

Replace `handleRunExperiment` with:

```javascript
  const handleRunExperiment = async (expId) => {
    const { config, errors } = buildConfig(expId, configForms[expId]);
    setValidationErrors(errors);
    setEvidenceExport(null);
    if (errors.length) return;

    setRunning(true);
    setError(null);
    try {
      const result = await experimentsApi.run(expId, config);
      setExperimentsData((prev) => ({ ...prev, [expId]: result }));
    } catch (err) {
      setError(err.message || `Failed to run ${expId}.`);
    } finally {
      setRunning(false);
    }
  };

  const handleExportEvidence = async (expId) => {
    const { config, errors } = buildConfig(expId, configForms[expId]);
    setValidationErrors(errors);
    if (errors.length) return;

    setError(null);
    try {
      const exported = await experimentsApi.exportEvidence(expId, config);
      setEvidenceExport(exported);
    } catch (err) {
      setError(err.message || `Failed to export evidence for ${expId}.`);
    }
  };
```

Add a field updater:

```javascript
  const updateConfig = (expId, key, value) => {
    setConfigForms((prev) => ({
      ...prev,
      [expId]: {
        ...prev[expId],
        [key]: value,
      },
    }));
  };
```

- [ ] **Step 7: Render configuration controls**

Inside the right-side result card, before result details, render:

```jsx
            <div className="card" style={{ background: 'var(--bg-surface)', padding: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: 'var(--text-primary)', fontWeight: 700 }}>
                <Settings2 size={16} style={{ color: 'var(--cyan-neon)' }} />
                Experiment Configuration
              </div>

              <div className="grid-2">
                {(selectedExpId === 'EXP-A' || selectedExpId === 'EXP-D') && (
                  <div className="form-group">
                    <label className="form-label">Samples</label>
                    <input className="form-input" type="number" min="1" value={configForms[selectedExpId].n_samples} onChange={(e) => updateConfig(selectedExpId, 'n_samples', e.target.value)} />
                  </div>
                )}
                {selectedExpId === 'EXP-B' && (
                  <>
                    <div className="form-group">
                      <label className="form-label">Noise Levels</label>
                      <input className="form-input" value={configForms[selectedExpId].noise_levels} onChange={(e) => updateConfig(selectedExpId, 'noise_levels', e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Repetitions</label>
                      <input className="form-input" type="number" min="1" value={configForms[selectedExpId].n_repetitions} onChange={(e) => updateConfig(selectedExpId, 'n_repetitions', e.target.value)} />
                    </div>
                  </>
                )}
                {selectedExpId === 'EXP-C' && (
                  <div className="form-group">
                    <label className="form-label">Ledger Blocks</label>
                    <input className="form-input" type="number" min="1" value={configForms[selectedExpId].n_blocks} onChange={(e) => updateConfig(selectedExpId, 'n_blocks', e.target.value)} />
                  </div>
                )}
                <div className="form-group">
                  <label className="form-label">Seed</label>
                  <input className="form-input" type="number" value={configForms[selectedExpId].random_state} onChange={(e) => updateConfig(selectedExpId, 'random_state', e.target.value)} />
                </div>
              </div>

              {validationErrors.length > 0 && (
                <Alert type="warning" title="Invalid configuration">
                  {validationErrors.join(' ')}
                </Alert>
              )}
            </div>
```

- [ ] **Step 8: Render Research Lab panels for completed results**

Below the existing result-specific metric rendering, add:

```jsx
                {selectedResult?.trust_profile && (
                  <TrustProfileBars dimensions={selectedResult.trust_profile} />
                )}

                {selectedResult?.run_manifest && (
                  <ReproducibilityPanel result={selectedResult} />
                )}

                {selectedResult?.run_manifest && (
                  <div className="card" style={{ background: 'var(--bg-surface)' }}>
                    <div className="card-header">
                      <div>
                        <div className="card-title">
                          <PackageCheck size={16} style={{ color: 'var(--cyan-neon)' }} />
                          Evidence Package
                        </div>
                        <div className="card-subtitle">Export structured evidence for independent inspection</div>
                      </div>
                      <button className="btn btn-secondary" onClick={() => handleExportEvidence(selectedExpId)}>
                        <Download size={14} />
                        Export Evidence
                      </button>
                    </div>
                    {evidenceExport && evidenceExport.experiment_id === selectedExpId && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.8rem' }}>
                        <div>Package Path: <span className="hash-pill">{evidenceExport.package_path}</span></div>
                        <div>Package Hash: <span className="hash-pill">{evidenceExport.package_hash}</span></div>
                        <div>Files: {evidenceExport.files.join(', ')}</div>
                      </div>
                    )}
                  </div>
                )}
```

- [ ] **Step 9: Keep synthetic-data disclaimer visible**

Replace the final info alert with:

```jsx
            <Alert type="info">
              Research Lab v1 uses deterministic experiment configurations, canonical SHA-256 result hashes, and reproducibility manifests. Current benchmark datasets are synthetic unless a manifest states otherwise.
            </Alert>
```

- [ ] **Step 10: Run frontend build**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 11: Commit Task 4**

Run:

```bash
git add frontend/src/api/experiments.js frontend/src/pages/Experiments.jsx frontend/src/components/research/TrustProfileBars.jsx frontend/src/components/research/ReproducibilityPanel.jsx
git commit -m "feat: upgrade experiments page to research lab"
```

---

### Task 5: Professor Mode Frontend

**Files:**
- Create: `frontend/src/pages/ProfessorMode.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/layout/Sidebar.jsx`

**Interfaces:**
- Consumes: `experimentsApi.presentationSummary() -> Promise<object>`
- Consumes: `experimentsApi.run('EXP-C', config) -> Promise<object>`
- Produces: route `/professor-mode`

- [ ] **Step 1: Create ProfessorMode page**

Create `frontend/src/pages/ProfessorMode.jsx`:

```jsx
import React, { useEffect, useState } from 'react';
import { BookOpenCheck, FlaskConical, Play, ShieldCheck, AlertTriangle, ArrowRight } from 'lucide-react';
import Alert from '../components/common/Alert';
import Loader from '../components/common/Loader';
import StatusBadge from '../components/common/StatusBadge';
import { experimentsApi } from '../api/experiments';

function Section({ title, icon: Icon, children }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <Icon size={16} style={{ color: 'var(--cyan-neon)' }} />
          {title}
        </div>
      </div>
      {children}
    </div>
  );
}

export default function ProfessorMode() {
  const [summary, setSummary] = useState(null);
  const [expC, setExpC] = useState(null);
  const [loading, setLoading] = useState(true);
  const [runningDemo, setRunningDemo] = useState(false);
  const [error, setError] = useState(null);

  const loadSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await experimentsApi.presentationSummary();
      setSummary(data);
    } catch (err) {
      setError(err.message || 'Failed to load presentation summary.');
    } finally {
      setLoading(false);
    }
  };

  const runTamperDemo = async () => {
    setRunningDemo(true);
    setError(null);
    try {
      const result = await experimentsApi.run('EXP-C', { n_blocks: 50, random_state: 42 });
      setExpC(result);
      await loadSummary();
    } catch (err) {
      setError(err.message || 'Failed to run EXP-C tamper demonstration.');
    } finally {
      setRunningDemo(false);
    }
  };

  useEffect(() => {
    loadSummary();
  }, []);

  if (loading) {
    return <Loader text="Loading professor presentation mode..." />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)' }}>Professor Mode</h2>
          <p style={{ fontSize: '0.84rem', color: 'var(--text-muted)' }}>
            A compact research presentation view backed by stored SentinelCrypt experiment evidence.
          </p>
        </div>
        <button className="btn btn-primary" onClick={runTamperDemo} disabled={runningDemo}>
          <Play size={14} className={runningDemo ? 'spinner' : ''} />
          {runningDemo ? 'Running EXP-C...' : 'Run Tamper Demo'}
        </button>
      </div>

      {error && <Alert type="danger" title="Professor Mode Error">{error}</Alert>}

      <Section title="Research Question" icon={BookOpenCheck}>
        <div style={{ fontSize: '1rem', color: 'var(--text-primary)', lineHeight: 1.6 }}>
          {summary?.research_question}
        </div>
      </Section>

      <div className="grid-2">
        <Section title="Methodology" icon={FlaskConical}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {(summary?.methodology || []).map((item, index) => (
              <div key={item} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', color: 'var(--text-secondary)', fontSize: '0.84rem' }}>
                <span className="badge badge-info">{index + 1}</span>
                <span>{item}</span>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Trustworthy ML Pipeline" icon={ShieldCheck}>
          <div className="table-container">
            <table className="table">
              <tbody>
                <tr><td>Datasets</td><td>{(summary?.datasets || []).map((d) => `${d.name} (${d.status})`).join(', ')}</td></tr>
                <tr><td>Models</td><td>{(summary?.models || []).join(', ')}</td></tr>
                <tr><td>XAI Method</td><td>{summary?.xai_method}</td></tr>
                <tr><td>Evidence</td><td>{summary?.cryptographic_evidence}</td></tr>
              </tbody>
            </table>
          </div>
        </Section>
      </div>

      <Section title="Experiments and Results" icon={FlaskConical}>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Experiment</th>
                <th>Status</th>
                <th>Latest Evidence Highlight</th>
              </tr>
            </thead>
            <tbody>
              {(summary?.experiments || []).map((experiment) => (
                <tr key={experiment.experiment_id}>
                  <td className="font-mono">{experiment.experiment_id}</td>
                  <td><StatusBadge status={experiment.status === 'COMPLETED' ? 'success' : 'pending'} label={experiment.status} /></td>
                  <td>{experiment.highlight}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Controlled Tampering Demonstration" icon={AlertTriangle}>
        {!expC ? (
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.86rem' }}>
            Run EXP-C to build a synthetic ledger, verify it, simulate controlled tampering, and show the detected failure locations.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <span className="badge badge-benign">Clean Chain: {expC.metrics?.clean_chain_valid ? 'Verified' : 'Failed'}</span>
              <span className="badge badge-info">Detection Rate: {expC.metrics?.tamper_detection_rate}</span>
              <span className="hash-pill">{expC.result_hash}</span>
            </div>
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Scenario</th>
                    <th>Target</th>
                    <th>Detected At</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(expC.metrics?.attacks_simulated || []).map((attack) => (
                    <tr key={attack.attack_type}>
                      <td>{attack.attack_type}</td>
                      <td className="font-mono">#{attack.tampered_sequence}</td>
                      <td className="font-mono">#{attack.detected_at_sequence}</td>
                      <td><StatusBadge status={attack.detected ? 'verified' : 'failed'} label={attack.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Section>

      <div className="grid-2">
        <Section title="Limitations" icon={AlertTriangle}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {(summary?.limitations || []).map((item) => (
              <div key={item} style={{ color: 'var(--text-secondary)', fontSize: '0.84rem' }}>
                <ArrowRight size={13} style={{ marginRight: '8px', color: 'var(--status-warning)' }} />
                {item}
              </div>
            ))}
          </div>
        </Section>

        <Section title="Future Work" icon={BookOpenCheck}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {(summary?.future_work || []).map((item) => (
              <div key={item} style={{ color: 'var(--text-secondary)', fontSize: '0.84rem' }}>
                <ArrowRight size={13} style={{ marginRight: '8px', color: 'var(--cyan-neon)' }} />
                {item}
              </div>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add route**

Modify `frontend/src/App.jsx`:

```javascript
import ProfessorMode from './pages/ProfessorMode';
```

Add route inside the existing nested routes:

```jsx
          <Route path="professor-mode" element={<ProfessorMode />} />
```

- [ ] **Step 3: Update sidebar navigation**

Modify imports in `frontend/src/components/layout/Sidebar.jsx`:

```javascript
  Presentation,
```

Change the research nav array:

```javascript
  const researchNav = [
    { name: 'Research Lab', path: '/experiments', icon: FlaskConical },
    { name: 'Professor Mode', path: '/professor-mode', icon: Presentation },
    { name: 'Documentation', path: '/docs', icon: FileText },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];
```

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

Run:

```bash
git add frontend/src/pages/ProfessorMode.jsx frontend/src/App.jsx frontend/src/components/layout/Sidebar.jsx
git commit -m "feat: add professor mode presentation view"
```

---

### Task 6: Full Verification and Final Polish

**Files:**
- Modify only files that fail verification due to syntax, route ordering, import, or formatting issues from Tasks 1-5.

**Interfaces:**
- Consumes: all interfaces from Tasks 1-5.
- Produces: verified backend and frontend implementation.

- [ ] **Step 1: Run backend experiment unit tests**

Run:

```bash
pytest backend/tests/unit/test_experiments.py -v
```

Expected: PASS.

- [ ] **Step 2: Run backend experiment API integration tests**

Run:

```bash
pytest backend/tests/integration/test_experiment_api.py -v
```

Expected: PASS.

- [ ] **Step 3: Run the full backend test suite**

Run:

```bash
pytest backend/tests -v
```

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 5: Verify no accidental generated artifacts are staged**

Run:

```bash
git status --short
```

Expected: source files and intentional docs may be modified; generated result JSON, `sentinelcrypt.db`, and `results/evidence/` should not be staged unless explicitly requested.

- [ ] **Step 6: Commit verification polish if changes were needed**

If Step 1-4 required fixes, run:

```bash
git add backend/app/services/experiment_service.py backend/app/api/v1/experiments.py backend/tests/unit/test_experiments.py backend/tests/integration/test_experiment_api.py frontend/src
git commit -m "fix: polish research lab verification"
```

If no fixes were needed, do not create an empty commit.

- [ ] **Step 7: Final implementation summary**

Report:

```text
Implemented Research Lab v1 and Professor Mode.
Backend verification: <exact pytest command and result>
Frontend verification: <exact npm command and result>
Evidence export path shape: results/evidence/<experiment-id>/
Known limitations: current experiments use synthetic data; ledger is tamper-evident, not tamper-proof; app remains a research prototype.
```

---

## Self-Review

Spec coverage:

- Research Lab configuration controls are covered in Task 4.
- Backend reproducibility manifest, hashes, and trust profile are covered in Task 1.
- Evidence package export is covered in Task 2.
- Presentation summary and route ordering are covered in Task 3.
- Professor/Demo Mode is covered in Task 5.
- Verification and artifact hygiene are covered in Task 6.

Type consistency:

- All new service method names are defined in Task 1 or Task 2 before frontend or API usage.
- `presentation-summary` route is defined before `/{exp_id}` as required.
- Frontend API method names match their usage: `exportEvidence` and `presentationSummary`.

Scope:

- This plan does not add statistical testing, OOD detection, unknown attack mode, AI assistant, digital signatures, real dataset feature mapping, or ZIP export.
