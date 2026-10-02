"""Tests for the standardized benchmark suite."""
import json

import pytest

from backend.app.research import benchmark
from backend.app.cryptography.hashing import sha256_hash
from backend.app.cryptography.canonicalization import canonicalize


def test_run_benchmark_covers_sources_and_metrics():
    report = benchmark.run_benchmark(n_samples=500, seed=42, repeats=2)
    assert report["status"] == "COMPLETED"
    assert len(report["sources"]) == 3  # unsw proxy, cicids proxy, controlled

    row = report["sources"][0]
    ind = row["in_distribution"]
    for metric in ("f1", "f1_macro", "precision", "recall", "pr_auc", "ece",
                   "inference_latency_ms", "train_peak_memory_mb",
                   "explanation_stability"):
        assert metric in ind, f"missing {metric}"

    # OOD arm measured
    assert "f1" in row["out_of_distribution"]
    assert "delta_f1" in row["generalization_gap"]

    # ledger overhead measured
    assert row["ledger_overhead"]["chain_valid"] is True
    assert row["ledger_overhead"]["verify_us_per_block"] > 0

    # reproducibility across identical-seed reruns
    repro = row["reproducibility"]
    assert repro["repeats"] == 2
    assert repro["f1_spread"] < 1e-9  # deterministic seeds → identical F1
    assert repro["bit_identical_across_runs"] is True

    # report is hashed and persisted
    assert len(report["report_hash"]) == 64
    latest = benchmark.latest_report()
    assert latest["benchmark_id"] == report["benchmark_id"]


def test_benchmark_report_markdown_written():
    benchmark.run_benchmark(n_samples=400, seed=42, repeats=1)
    md = benchmark.RESULTS_DIR / "reports" / "benchmark_latest.md"
    assert md.exists()
    text = md.read_text(encoding="utf-8")
    assert "SentinelCrypt Benchmark Report" in text
    assert "synthetic" in text.lower()  # honest origin labelling


def test_unknown_source_rejected():
    with pytest.raises(ValueError, match="Unknown benchmark source"):
        benchmark.run_protocol("mnist", n_samples=100)


def test_pipeline_benchmark_measures_all_seven_stages():
    result = benchmark.run_pipeline_benchmark(n_samples=400, seed=42)
    for stage in ("dataset_ingestion", "preprocessing", "prediction", "shap",
                  "evidence_generation", "ledger_write", "verification"):
        assert stage in result["stages_ms"]
        assert result["stages_ms"][stage] >= 0
    assert result["end_to_end_ms"] > 0
    assert 0 <= result["xai_overhead_pct"] <= 100
    assert 0 <= result["crypto_overhead_pct"] <= 100
    assert result["chain_valid"] is True


def test_scalability_sweep_custom_ladder():
    result = benchmark.run_scalability(sizes=[100, 300], seed=42)
    points = result["points"]
    assert [p["n_samples"] for p in points] == [100, 300]
    for point in points:
        assert point["train_time_s"] > 0
        assert point["predict_throughput_rows_per_s"] > 0
        assert point["peak_memory_mb"] > 0
    # scaling exponents computed (or None if insufficient points)
    assert "scaling_exponents" in result
    assert len(result["result_hash"]) == 64


def test_scalability_rejects_nonpositive_sizes():
    with pytest.raises(ValueError):
        benchmark.run_scalability(sizes=[0])


def test_leaderboard_rows_and_filters():
    benchmark.run_benchmark(n_samples=300, seed=42, repeats=1)
    board = benchmark.leaderboard()
    assert board["total"] == len(board["rows"])
    assert board["rows"], "leaderboard should include stored experiment results"

    # every row carries the transparent table fields
    for row in board["rows"]:
        assert {"experiment", "dataset", "model", "f1",
                "latency_us", "xai_stability"} <= set(row)

    # filter works
    filtered = benchmark.leaderboard(experiment_filter="EXP-A")
    assert all(r["experiment"] == "EXP-A" for r in filtered["rows"])

    # sorted by F1 where present
    f1s = [r["f1"] for r in board["rows"] if r["f1"] is not None]
    assert f1s == sorted(f1s, reverse=True)


def test_benchmark_sources_are_labelled_honestly():
    for key, spec in benchmark.BENCHMARK_SOURCES.items():
        if key in ("unsw_nb15", "cicids2017"):
            assert spec["origin"] == "synthetic_proxy"
            assert "not real" in spec["note"].lower()
