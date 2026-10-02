"""Research endpoints: challenges, model selection, notary, robustness,
provenance graph, trust checklist, reproducibility, plugins, and app modes."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.database import get_db

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Research challenges (items: challenge framework, Q1-Q5, longitudinal, repro)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/challenges/presets", summary="Preset research questions Q1–Q5",
            response_model=Dict[str, Any])
def challenge_presets() -> Dict[str, Any]:
    from backend.app.research.challenges import QUESTION_PRESETS
    return {"presets": QUESTION_PRESETS, "total": len(QUESTION_PRESETS)}


@router.post("/challenges/define", summary="Define a research challenge (hypothesis → package)",
             response_model=Dict[str, Any])
def define_challenge(spec: Dict[str, Any]) -> Dict[str, Any]:
    from backend.app.research.challenges import create_challenge
    try:
        return create_challenge(
            title=spec.get("title", ""),
            hypothesis=spec.get("hypothesis", ""),
            experiment=str(spec.get("experiment", "")).upper(),
            kind=spec.get("kind", "standard"),
            config=spec.get("config"),
            dataset_note=spec.get(
                "dataset_note",
                "Synthetic-scope protocol data (labelled synthetic).",
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/challenges/run", summary="Run a defined challenge or a Q1–Q5 preset",
             response_model=Dict[str, Any])
def run_challenge(spec: Dict[str, Any]) -> Dict[str, Any]:
    from backend.app.research.challenges import create_challenge, run_preset, run_challenge as _run

    try:
        preset = spec.get("preset")
        if preset:
            return run_preset(str(preset), n_runs=spec.get("n_runs"))
        challenge = create_challenge(
            title=spec.get("title", ""),
            hypothesis=spec.get("hypothesis", ""),
            experiment=str(spec.get("experiment", "")).upper(),
            kind=spec.get("kind", "standard"),
            config=spec.get("config"),
            dataset_note=spec.get(
                "dataset_note",
                "Synthetic-scope protocol data (labelled synthetic).",
            ),
        )
        return _run(challenge, n_runs=spec.get("n_runs"))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Challenge execution failed: {str(e)}",
        )


@router.get("/challenges", summary="List persisted research challenges",
            response_model=Dict[str, Any])
def list_challenges() -> Dict[str, Any]:
    from backend.app.research.challenges import list_challenges as _list
    items = _list()
    return {"challenges": items, "total": len(items)}


@router.get("/challenges/{challenge_id}", summary="Fetch one challenge result",
            response_model=Dict[str, Any])
def get_challenge(challenge_id: str) -> Dict[str, Any]:
    from backend.app.research.challenges import get_challenge as _get
    result = _get(challenge_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Challenge '{challenge_id}' not found.")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Model selection (item: measured candidate comparison)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/model-selection/candidates", summary="List CV candidate models",
            response_model=Dict[str, Any])
def model_candidates() -> Dict[str, Any]:
    from backend.app.research.model_selection import CANDIDATES, SCORING
    return {"candidates": sorted(CANDIDATES), "scoring": list(SCORING)}


@router.post("/model-selection/run", summary="Cross-validated model selection",
             response_model=Dict[str, Any])
def run_model_selection(spec: Optional[Dict[str, Any]] = None,
                        db: Session = Depends(get_db)) -> Dict[str, Any]:
    from backend.app.research.model_selection import select_model

    cfg = spec or {}
    try:
        dataset = None
        dataset_id = cfg.get("dataset_id")
        if dataset_id:
            import pandas as pd
            from pathlib import Path
            from backend.app.core.config import settings
            from backend.app.db.repositories.dataset_repository import DatasetRepository

            record = DatasetRepository(db).get_by_id(dataset_id)
            if not record:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                    detail=f"Dataset '{dataset_id}' not found.")
            csv_path = Path(settings.DATA_RAW_DIR) / record.file_name
            if not csv_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Dataset file missing at {csv_path.name}.",
                )
            dataset = pd.read_csv(csv_path)
        return select_model(
            dataset=dataset,
            target_column=cfg.get("target_column", "label"),
            candidates=cfg.get("candidates"),
            cv_folds=int(cfg.get("cv_folds", 5)),
            seed=int(cfg.get("seed", cfg.get("random_state", 42))),
            n_samples=int(cfg.get("n_samples", 800)),
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model selection failed: {str(e)}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Cryptographic research notary (item: sign + verify research artifacts)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/notary/public-key", summary="Notary public key + fingerprint",
            response_model=Dict[str, Any])
def notary_public_key() -> Dict[str, Any]:
    from backend.app.cryptography import notary
    return {
        "algorithm": notary.ALGORITHM,
        "digest_algorithm": notary.DIGEST_ALGORITHM,
        "public_key": notary.public_key_b64(),
        "fingerprint": notary.fingerprint(),
        "key_note": "Demo research keypair stored under results/notary/ — not a production PKI.",
    }


@router.post("/notary/sign", summary="Disabled: arbitrary payload signing is unsafe",
             response_model=Dict[str, Any])
def notary_sign(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Reject caller-supplied payloads so the notary cannot certify forged claims.

    Only ``/notary/sign-experiment`` may sign a server-retrieved experiment
    result.  This endpoint remains as an explicit 403 for clients using an
    older API contract rather than silently accepting an unsafe request.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "ARBITRARY_NOTARY_SIGNING_DISABLED",
            "message": (
                "Only stored, server-generated experiment results may be "
                "notarized."
            ),
        },
    )


@router.post("/notary/sign-experiment", summary="Notarize a stored experiment result",
             response_model=Dict[str, Any])
def notary_sign_experiment(spec: Dict[str, Any]) -> Dict[str, Any]:
    from backend.app.cryptography import notary
    from backend.app.services.experiment_service import ExperimentService

    exp_id = str(spec.get("experiment_id", "")).upper().strip()
    service = ExperimentService()
    try:
        result = service.get_experiment_by_id(exp_id)
    except Exception:
        result = None
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Experiment '{exp_id}' not found or not yet run.")
    return notary.sign_result(result)


@router.post("/notary/verify", summary="Verify an exported research artifact",
             response_model=Dict[str, Any])
def notary_verify(artifact: Dict[str, Any]) -> Dict[str, Any]:
    from backend.app.cryptography import notary
    return notary.verify_artifact(artifact)


# ─────────────────────────────────────────────────────────────────────────────
# Robustness study (item: bounded perturbation evaluation)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/robustness/run", summary="Bounded synthetic perturbation robustness study",
             response_model=Dict[str, Any])
def run_robustness(spec: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from backend.app.services.experiment_service import ExperimentService
    from backend.app.research.robustness import run_robustness_study

    cfg = spec or {}
    if "random_state" not in cfg and "seed" in cfg:
        cfg = {**cfg, "random_state": cfg["seed"]}
    try:
        normalized = ExperimentService().validate_experiment_config(
            "EXP-ROBUSTNESS", cfg
        )
        return run_robustness_study(
            n_samples=normalized["n_samples"],
            n_probe=normalized["n_probe"],
            epsilon_levels=normalized["epsilon_levels"],
            seed=normalized["random_state"],
            with_explanations=normalized["with_explanations"],
            n_repeats=normalized["n_repeats"],
            model_type=normalized["model_type"],
            experiment_id="ROBUSTNESS",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Provenance graph + trust checklist (items 16/17)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/provenance/graph", summary="Dataset→…→evidence provenance graph",
            response_model=Dict[str, Any])
def provenance_graph(db: Session = Depends(get_db)) -> Dict[str, Any]:
    from backend.app.research.provenance import build_provenance_graph
    return build_provenance_graph(db)


@router.get("/lineage", summary="Cryptographic artifact lineage graph",
            response_model=Dict[str, Any])
def artifact_lineage(db: Session = Depends(get_db)) -> Dict[str, Any]:
    from backend.app.services.lineage_service import (
        ArtifactLineageService,
        LineageIntegrityError,
    )
    try:
        return ArtifactLineageService(db).graph()
    except LineageIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "LINEAGE_INTEGRITY_ERROR", "message": str(exc)},
        ) from exc


@router.get("/provenance/node/{node_id:path}", summary="Inspect one provenance node",
            response_model=Dict[str, Any])
def provenance_node(node_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    from backend.app.research.provenance import node_detail
    node = node_detail(node_id, db=db)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Provenance node '{node_id}' not found.")
    return node


@router.get("/trust/prediction/{prediction_id}", summary="Trust checklist for a prediction",
            response_model=Dict[str, Any])
def prediction_trust(prediction_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    from backend.app.research.provenance import prediction_trust_checklist
    try:
        return prediction_trust_checklist(prediction_id, db=db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Reproducibility (items: manifest, cross-env compare, determinism)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/reproducibility/manifest", summary="Cross-environment manifest",
            response_model=Dict[str, Any])
def reproducibility_manifest(
    dataset_id: Optional[str] = Query(None),
    seed: int = Query(42),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    from backend.app.research.reproducibility import build_manifest
    return build_manifest(dataset_id=dataset_id, random_seed=seed, db=db)


@router.post("/reproducibility/compare", summary="Diff two environment manifests",
             response_model=Dict[str, Any])
def compare_manifests(spec: Dict[str, Any]) -> Dict[str, Any]:
    from backend.app.research.reproducibility import compare_manifests as _compare
    a, b = spec.get("a"), spec.get("b")
    if not isinstance(a, dict) or not isinstance(b, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Body must contain two manifest objects under keys 'a' and 'b'.",
        )
    return _compare(a, b)


# ─────────────────────────────────────────────────────────────────────────────
# Plugins (item: extension without core edits)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/plugins", summary="List registered plugins by kind",
            response_model=Dict[str, Any])
def list_plugins(kind: Optional[str] = Query(None)) -> Dict[str, Any]:
    from backend.app.plugins import PLUGIN_KINDS, get_registry
    registry = get_registry()
    try:
        plugins = registry.list(kind)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"plugins": plugins, "kinds": list(PLUGIN_KINDS), "counts": registry.counts()}


@router.post("/plugins/discover", summary="Reload plugin files from the local plugins/ directory",
             response_model=Dict[str, Any])
def discover_plugins() -> Dict[str, Any]:
    """Load ``plugins/*.py`` from the repository. This is not a remote install path."""
    from backend.app.plugins.registry import PLUGIN_DIR, discover_plugins as _discover
    from backend.app.plugins import get_registry

    return _discover(registry=get_registry(), directory=PLUGIN_DIR)


# ─────────────────────────────────────────────────────────────────────────────
# Database integrity audit (Devil's-Advocate phases 14/15)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/db-integrity", summary="Relational integrity audit (orphans, gaps, timelines, chain)",
            response_model=Dict[str, Any])
def db_integrity_audit(db: Session = Depends(get_db)) -> Dict[str, Any]:
    from backend.app.research.db_integrity import audit_database
    return audit_database(db)


# ─────────────────────────────────────────────────────────────────────────────
# Modes (item: Research Mode vs Demo Mode)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/mode", summary="Current application mode", response_model=Dict[str, Any])
def get_mode() -> Dict[str, Any]:
    from backend.app.research.modes import mode_state
    return mode_state()


@router.post("/mode", summary="Switch application mode", response_model=Dict[str, Any])
def set_mode(spec: Dict[str, Any]) -> Dict[str, Any]:
    from backend.app.research.modes import mode_state, set_mode as _set
    try:
        _set(str(spec.get("mode", "")))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return mode_state()
