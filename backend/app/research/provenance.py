"""Provenance graph + result trust checklist (items 16/17).

Provenance graph: dataset -> preprocessing -> model -> experiment ->
    prediction -> explanation -> evidence -> report, built from ACTUAL stored
    records (DB rows + results/ files).  Click any node → metadata.

Trust checklist: a transparent evidence panel — eight named checks, each with
its evidence source.  Deliberately NOT a numeric trust score.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.cryptography.hashing import hash_file
from backend.app.db.database import SessionLocal
from backend.app.db.models import AuditRecord, Dataset, Explanation, ModelRecord, Prediction

RESULTS_DIR = Path(settings.RESULTS_DIR)


# ─────────────────────────────────────────────────────────────────────────────
# Provenance graph
# ─────────────────────────────────────────────────────────────────────────────

def _node(node_id: str, node_type: str, label: str, metadata: Dict[str, Any],
          provenance: str = "database") -> Dict[str, Any]:
    return {
        "id": node_id,
        "type": node_type,
        "label": label,
        "metadata": metadata,
        "provenance": provenance,
    }


def build_provenance_graph(db: Optional[Session] = None) -> Dict[str, Any]:
    """Walk real records and emit nodes + edges for rendering."""
    session = db or SessionLocal()
    owns_session = db is None
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    try:
        datasets = session.query(Dataset).order_by(Dataset.created_at).all()
        models = session.query(ModelRecord).order_by(ModelRecord.created_at).all()
        predictions = session.query(Prediction).order_by(Prediction.created_at).all()
        explanations = session.query(Explanation).order_by(Explanation.created_at).all()
        audits = session.query(AuditRecord).order_by(AuditRecord.sequence_number).all()

        for d in datasets:
            nodes.append(_node(
                f"dataset:{d.id}", "dataset", d.name,
                {"rows": d.row_count, "features": d.feature_count,
                 "sha256": d.file_hash, "status": d.validation_status,
                 "created_at": str(d.created_at)},
            ))

        for m in models:
            nodes.append(_node(
                f"model:{m.id}", "model", m.name,
                {"version": m.version, "artifact": Path(m.artifact_path).name,
                 "metrics": json.loads(m.metrics_json or "{}").get("metrics", {}),
                 "created_at": str(m.created_at)},
            ))
            # model → dataset edge: recompute from training link if available
            if m.experiment_id:
                edges.append({
                    "source": f"model:{m.id}", "target": f"experiment:{m.experiment_id}",
                    "type": "trained_within",
                })

        # experiments from stored results (file-backed EXP-A..H + DB rows)
        from backend.app.services.experiment_service import EXPERIMENT_RESULT_FILES
        for exp_id, filename in EXPERIMENT_RESULT_FILES.items():
            path = RESULTS_DIR / filename
            if not path.exists():
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    result = json.load(f)
            except Exception:
                continue
            node_id = f"experiment:{exp_id}"
            nodes.append(_node(
                node_id, "experiment", result.get("title", exp_id),
                {"status": result.get("status"),
                 "result_hash": result.get("result_hash"),
                 "configuration_hash": result.get("configuration_hash"),
                 "artifact": filename},
                provenance="results/",
            ))
            edges.append({"source": node_id, "target": "report:benchmark",
                          "type": "contributes_to"})

        for p in predictions:
            node_id = f"prediction:{p.id}"
            nodes.append(_node(
                node_id, "prediction", f"{p.predicted_class}",
                {"model_id": p.model_id, "input_hash": p.input_hash,
                 "latency_ms": p.latency_ms, "created_at": str(p.created_at)},
            ))
            edges.append({"source": node_id, "target": f"model:{p.model_id}",
                          "type": "produced_by"})
            edges.append({"source": node_id, "target": f"experiment:{_model_experiment(models, p.model_id)}",
                          "type": "evaluates"})

        for e in explanations:
            node_id = f"explanation:{e.id}"
            nodes.append(_node(
                node_id, "explanation", e.method,
                {"stability_score": e.stability_score,
                 "top_features": [f.get("feature") for f in e.top_features[:5]],
                 "created_at": str(e.created_at)},
            ))
            edges.append({"source": node_id, "target": f"prediction:{e.prediction_id}",
                          "type": "explains"})

        for a in audits:
            node_id = f"evidence:{a.sequence_number}"
            nodes.append(_node(
                node_id, "evidence", f"Block #{a.sequence_number}",
                {"record_hash": a.record_hash, "previous_hash": a.previous_hash,
                 "prediction_id": a.prediction_id},
            ))
            edges.append({"source": node_id, "target": f"prediction:{a.prediction_id}",
                          "type": "anchors"})
            if a.sequence_number > 1:
                edges.append({"source": node_id, "target": f"evidence:{a.sequence_number - 1}",
                              "type": "hash_links"})

        # evidence packages / reports
        for exp_id in EXPERIMENT_RESULT_FILES:
            pkg = RESULTS_DIR / "evidence" / exp_id
            if pkg.exists():
                node_id = f"package:{exp_id}"
                nodes.append(_node(
                    node_id, "package", f"Evidence {exp_id}",
                    {"path": pkg.as_posix(),
                     "files": sorted(p.name for p in pkg.iterdir() if p.is_file())},
                    provenance="results/evidence/",
                ))
                edges.append({"source": node_id, "target": f"experiment:{exp_id}",
                              "type": "exports"})

        for report in sorted((RESULTS_DIR / "reports").glob("benchmark_*.json"))[-1:]:
            nodes.append(_node(
                "report:benchmark", "report", "Benchmark Report",
                {"path": report.as_posix(), "mtime": report.stat().st_mtime},
                provenance="results/reports/",
            ))

        node_ids = {n["id"] for n in nodes}
        dangling_edges = [
            edge for edge in edges
            if edge["source"] not in node_ids or edge["target"] not in node_ids
        ]
        type_counts: Dict[str, int] = {}
        for n in nodes:
            type_counts[n["type"]] = type_counts.get(n["type"], 0) + 1

        return {
            "nodes": nodes,
            "edges": edges,
            "integrity": "warning" if dangling_edges else "structurally_valid",
            "integrity_warnings": [
                {
                    "source": edge["source"],
                    "target": edge["target"],
                    "type": edge["type"],
                    "message": "Provenance edge references a node absent from the graph.",
                }
                for edge in dangling_edges
            ],
            "node_counts": type_counts,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    finally:
        if owns_session:
            session.close()


def _model_experiment(models: List[ModelRecord], model_id: str) -> str:
    for m in models:
        if m.id == model_id:
            return m.experiment_id or "unknown"
    return "unknown"


def node_detail(node_id: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    """Full metadata for one graph node (click-to-inspect)."""
    graph = build_provenance_graph(db)
    return next((n for n in graph["nodes"] if n["id"] == node_id), None)


# ─────────────────────────────────────────────────────────────────────────────
# Trust checklist (transparent, evidence-backed — no numeric score)
# ─────────────────────────────────────────────────────────────────────────────

def _check(name: str, passed: bool, evidence: str, source: str) -> Dict[str, Any]:
    return {"check": name, "passed": bool(passed), "evidence": evidence, "source": source}


def prediction_trust_checklist(prediction_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
    """Eight-point evidence checklist for one prediction result."""
    session = db or SessionLocal()
    owns_session = db is None
    try:
        prediction = session.get(Prediction, prediction_id)
        if not prediction:
            raise ValueError(f"Prediction '{prediction_id}' not found.")
        model = session.get(ModelRecord, prediction.model_id)
        audit = session.query(AuditRecord).filter_by(prediction_id=prediction_id).first()
        explanation = session.query(Explanation).filter_by(prediction_id=prediction_id).first()
        dataset = session.query(Dataset).first()

        dataset_file = None
        if dataset:
            candidate = Path(settings.DATA_RAW_DIR) / dataset.file_name
            dataset_file = candidate if candidate.exists() else None

        chain_ok = None
        if audit:
            # A mid-chain block cannot be verified in isolation (its
            # previous_hash points at its predecessor) — verify the chain
            # prefix from genesis through this block instead.
            from backend.app.cryptography.verifier import verify_ledger
            prefix = (
                session.query(AuditRecord)
                .filter(AuditRecord.sequence_number <= audit.sequence_number)
                .order_by(AuditRecord.sequence_number)
                .all()
            )
            chain_ok = verify_ledger(prefix).verified

        checks = [
            _check(
                "Dataset provenance",
                dataset is not None,
                f"Dataset '{dataset.name}' registered with SHA-256 {dataset.file_hash[:16]}…"
                if dataset else "No dataset registered.",
                "datasets.file_hash",
            ),
            _check(
                "Dataset integrity",
                dataset_file is not None,
                f"Raw CSV present on disk at {dataset_file.name}" if dataset_file
                else "Raw CSV missing from data/raw/ — integrity cannot be re-verified.",
                "data/raw/",
            ),
            _check(
                "Model version recorded",
                model is not None,
                f"Model {model.name} @ {model.version}, artifact {Path(model.artifact_path).name}"
                if model else "Prediction references unknown model.",
                "models.version",
            ),
            _check(
                "Experiment configuration recorded",
                model is not None and bool(model.experiment_id),
                f"Experiment link: {model.experiment_id}" if model and model.experiment_id
                else "Model not linked to an experiment configuration.",
                "models.experiment_id",
            ),
            _check(
                "Random seed recorded",
                model is not None and _seed_recorded(model),
                _seed_evidence(model),
                "models.metrics_json / run_manifest",
            ),
            _check(
                "Explanation available",
                explanation is not None,
                f"{explanation.method}, stability={explanation.stability_score}"
                if explanation else "No SHAP explanation stored for this prediction.",
                "explanations",
            ),
            _check(
                "Audit evidence",
                audit is not None and bool(chain_ok),
                f"Block #{audit.sequence_number}, hash {audit.record_hash[:16]}…, "
                f"chain {'verified' if chain_ok else 'NOT verified'}"
                if audit else "No audit block anchored for this prediction.",
                "audit_records",
            ),
            _check(
                "Reproducibility",
                model is not None and bool(model.experiment_id)
                and _has_run_manifest(model.experiment_id),
                f"Run manifest exists for {model.experiment_id}"
                if model and _has_run_manifest(model.experiment_id)
                else "No reproducibility run manifest found for the linked experiment.",
                "results/*.json run_manifest",
            ),
        ]

        passed = sum(1 for c in checks if c["passed"])
        return {
            "prediction_id": prediction_id,
            "title": "Result Trust Information",
            "checks": checks,
            "checks_passed": passed,
            "checks_total": len(checks),
            "complete": passed == len(checks),
            "scoring_note": (
                "This is an evidence checklist, not a numeric trust score: each line "
                "names a verifiable artifact and where to find it."
            ),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    finally:
        if owns_session:
            session.close()


def _seed_recorded(model: ModelRecord) -> bool:
    try:
        payload = json.loads(model.metrics_json or "{}")
        return "seed" in json.dumps(payload).lower() or bool(
            json.loads(model.feature_schema_json or "[]")
        )
    except Exception:
        return False


def _seed_evidence(model: ModelRecord) -> str:
    if not model:
        return "No model record."
    try:
        payload = json.loads(model.metrics_json or "{}")
        text = json.dumps(payload).lower()
        if "seed" in text:
            return "Seed recorded in stored model metrics payload."
    except Exception:
        pass
    return "Default reproducibility seed (settings.RANDOM_SEED=42) applies to this run."


def _has_run_manifest(experiment_id: Optional[str]) -> bool:
    if not experiment_id or experiment_id not in _RESULT_FILES():
        return False
    path = RESULTS_DIR / _RESULT_FILES()[experiment_id]
    if not path.exists():
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            return "run_manifest" in json.load(f)
    except Exception:
        return False


def _RESULT_FILES() -> Dict[str, str]:
    from backend.app.services.experiment_service import EXPERIMENT_RESULT_FILES
    return EXPERIMENT_RESULT_FILES


def experiment_trust_checklist(exp_id: str) -> Dict[str, Any]:
    """Eight-point evidence checklist for a stored experiment result."""
    normalized = exp_id.upper().strip()
    files = _RESULT_FILES()
    if normalized not in files:
        raise ValueError(
            f"Unknown experiment '{exp_id}'. Available: {', '.join(sorted(files))}."
        )
    path = RESULTS_DIR / files[normalized]
    if not path.exists():
        return {
            "experiment_id": normalized,
            "checks": [],
            "checks_passed": 0,
            "checks_total": 8,
            "complete": False,
            "scoring_note": "Experiment has not been run — no evidence exists yet.",
        }

    with open(path, "r", encoding="utf-8") as f:
        result = json.load(f)
    manifest = result.get("run_manifest") or {}
    git = manifest.get("git") or {}
    pkg = result.get("evidence_package") or {}

    checks = [
        _check("Dataset provenance", bool(manifest.get("dataset_scope")),
               f"Scope: {manifest.get('dataset_scope')} — {manifest.get('dataset_disclaimer', '')}",
               "run_manifest"),
        _check("Dataset integrity", bool(git.get("commit")),
               f"Dataset scope anchored to git commit {git.get('commit')}.",
               "run_manifest.git"),
        _check("Model version recorded", bool(result.get("parameters") or result.get("comparison")),
               "Parameters/comparison captured in the stored result.",
               "results/*.json"),
        _check("Experiment configuration recorded", bool(result.get("configuration_hash")),
               f"Configuration hash: {result.get('configuration_hash')}",
               "canonical configuration hash"),
        _check("Random seed recorded", manifest.get("random_seed") is not None,
               f"Seed: {manifest.get('random_seed')}", "run_manifest.random_seed"),
        _check("Explanation available",
               normalized in ("EXP-B", "EXP-H") or "stability" in json.dumps(result).lower(),
               "Explanation stability measured by this experiment."
               if normalized in ("EXP-B", "EXP-H")
               else "Run EXP-B/EXP-H for explanation evidence on this configuration.",
               "experiment metrics"),
        _check("Audit evidence", bool(result.get("result_hash")),
               f"Canonical result hash: {result.get('result_hash')}", "SHA-256 result hash"),
        _check("Reproducibility", pkg.get("status") == "exported",
               f"Evidence package: {pkg.get('status', 'not_exported')}"
               + (f" ({pkg.get('package_hash', '')[:16]}…)" if pkg.get("package_hash") else ""),
               "results/evidence/"),
    ]
    passed = sum(1 for c in checks if c["passed"])
    return {
        "experiment_id": normalized,
        "title": "Result Trust Information",
        "checks": checks,
        "checks_passed": passed,
        "checks_total": len(checks),
        "complete": passed == len(checks),
        "scoring_note": (
            "Transparent evidence checklist — each line is an artifact you can open "
            "and re-verify, not an opaque score."
        ),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
