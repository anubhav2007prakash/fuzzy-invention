# SentinelCrypt Benchmark Report — BENCH-2026-09-24-124303

Generated: 2026-09-24T07:13:03Z  
Model: `RandomForestClassifier(n_estimators=50, max_depth=8)`  
Seed: 42 · repeats: 1  
Report hash: `074935ff38c990e1071d9151fefada5fd7962c0384b34cafe5760b1cac23f298`

## Protocol metrics
f1, f1_macro, precision, recall, pr_auc, roc_auc, ece, brier, inference_latency_ms, train/infer peak memory MB, explanation_stability, explanation_time_ms, OOD delta_f1, ledger append/verify us per block, repeatability spread

## Results

| Source | Origin | F1 | Macro-F1 | Precision | Recall | PR-AUC | ECE | Latency ms | Stability | OOD ΔF1 | F1 spread |
|---|---|---|---|---|---|---|---|---|---|---|---|
| UNSW-NB15 (distribution-matched synthetic proxy) | synthetic_proxy | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0001 | 0.0365 | 1.0 | 0.0000 | 0.0 |
| CICIDS2017 (distribution-matched synthetic proxy) | synthetic_proxy | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0003 | 0.0317 | 1.0 | 0.0000 | 0.0 |
| Controlled test data (labelled synthetic) | synthetic_controlled | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0006 | 0.0339 | 1.0 | 0.0000 | 0.0 |

## Summary

- **f1**: {'mean': 1.0, 'min': 1.0, 'max': 1.0}
- **f1_macro**: {'mean': 1.0, 'min': 1.0, 'max': 1.0}
- **precision**: {'mean': 1.0, 'min': 1.0, 'max': 1.0}
- **recall**: {'mean': 1.0, 'min': 1.0, 'max': 1.0}
- **pr_auc**: {'mean': 1.0, 'min': 1.0, 'max': 1.0}
- **ece**: {'mean': 0.000355, 'min': 0.000133, 'max': 0.0006}
- **inference_latency_ms**: {'mean': 0.034037, 'min': 0.031739, 'max': 0.036501}
- **explanation_stability**: {'mean': 1.0, 'min': 1.0, 'max': 1.0}
- **mean_ood_f1_drop**: 0.0
- **max_repeatability_spread**: 0.0
- **sources_evaluated**: 3

> Data-origin note: proxy sources are distribution-matched synthetic data, clearly labelled — not real UNSW-NB15/CICIDS2017 captures.
