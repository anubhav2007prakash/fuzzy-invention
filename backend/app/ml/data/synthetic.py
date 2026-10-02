"""Synthetic network-flow generator (item: controlled test data for tests/benchmarks).

Everything produced here is SYNTHETIC — clearly labelled, never presented as real
network telemetry.  Supports the controls research needs:
  * class imbalance via ``attack_ratio``
  * missing values via ``missing_rate``
  * distribution shift via ``shift_scale``
  * deterministic replay via ``random_state``

The default RNG call sequence is byte-compatible with the original
``ExperimentService.generate_synthetic_flow_dataset`` implementation, so existing
EXP-A..D results reproduce identically.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

SYNTHETIC_DISCLAIMER = (
    "Synthetic network-flow data with controlled properties. "
    "Not real network telemetry (not real UNSW-NB15 or CICIDS2017 captures)."
)


def generate_flow_dataset(
    n_samples: int = 1000,
    random_state: int = 42,
    shift_scale: float = 1.0,
    attack_ratio: float = 0.3,
    missing_rate: float = 0.0,
) -> pd.DataFrame:
    """Generate a deterministic synthetic flow dataset matching the UNSW/CICIDS feature schema."""
    if n_samples <= 0:
        raise ValueError("n_samples must be positive.")
    if not 0.0 <= attack_ratio <= 1.0:
        raise ValueError("attack_ratio must be within [0, 1].")
    if not 0.0 <= missing_rate < 1.0:
        raise ValueError("missing_rate must be within [0, 1).")

    rng = np.random.RandomState(random_state)
    n_attacks = int(n_samples * attack_ratio)
    n_benign = n_samples - n_attacks

    # Benign features
    benign_dur = rng.exponential(scale=0.5 * shift_scale, size=n_benign)
    benign_spkts = rng.poisson(lam=10 * shift_scale, size=n_benign) + 1
    benign_dpkts = rng.poisson(lam=12 * shift_scale, size=n_benign)
    benign_sbytes = benign_spkts * rng.randint(60, 500, size=n_benign)
    benign_dbytes = benign_dpkts * rng.randint(60, 1500, size=n_benign)
    benign_rate = (benign_spkts + benign_dpkts) / (benign_dur + 0.001)
    benign_sttl = rng.choice([64, 128], size=n_benign)
    benign_dttl = rng.choice([64, 128], size=n_benign)
    benign_sload = (benign_sbytes * 8) / (benign_dur + 0.001)
    benign_dload = (benign_dbytes * 8) / (benign_dur + 0.001)

    # Attack features
    atk_dur = rng.exponential(scale=0.05 * shift_scale, size=n_attacks)
    atk_spkts = rng.poisson(lam=45 * shift_scale, size=n_attacks) + 10
    atk_dpkts = rng.poisson(lam=2 * shift_scale, size=n_attacks)
    atk_sbytes = atk_spkts * rng.randint(40, 100, size=n_attacks)
    atk_dbytes = atk_dpkts * rng.randint(0, 100, size=n_attacks)
    atk_rate = (atk_spkts + atk_dpkts) / (atk_dur + 0.0001)
    atk_sttl = rng.choice([254, 255], size=n_attacks)
    atk_dttl = rng.choice([0, 32], size=n_attacks)
    atk_sload = (atk_sbytes * 8) / (atk_dur + 0.0001)
    atk_dload = (atk_dbytes * 8) / (atk_dur + 0.0001)

    df_benign = pd.DataFrame({
        "dur": benign_dur, "spkts": benign_spkts, "dpkts": benign_dpkts,
        "sbytes": benign_sbytes, "dbytes": benign_dbytes, "rate": benign_rate,
        "sttl": benign_sttl, "dttl": benign_dttl, "sload": benign_sload,
        "dload": benign_dload, "label": 0,
    })
    df_attack = pd.DataFrame({
        "dur": atk_dur, "spkts": atk_spkts, "dpkts": atk_dpkts,
        "sbytes": atk_sbytes, "dbytes": atk_dbytes, "rate": atk_rate,
        "sttl": atk_sttl, "dttl": atk_dttl, "sload": atk_sload,
        "dload": atk_dload, "label": 1,
    })

    df = pd.concat([df_benign, df_attack], ignore_index=True)
    df = df.sample(frac=1.0, random_state=random_state).reset_index(drop=True)

    if missing_rate > 0.0:
        # Separate RNG stream so the base sequence above stays untouched.
        miss_rng = np.random.RandomState(random_state + 7919)
        feature_cols = [c for c in df.columns if c != "label"]
        n_cells = int(df[feature_cols].size * missing_rate)
        if n_cells > 0:
            rows = miss_rng.randint(0, len(df), size=n_cells)
            col_positions = [df.columns.get_loc(c) for c in feature_cols]
            cols = miss_rng.randint(0, len(col_positions), size=n_cells)
            for r, c_idx in zip(rows, cols):
                df.iat[int(r), col_positions[int(c_idx)]] = np.nan

    df.attrs["synthetic"] = True
    df.attrs["disclaimer"] = SYNTHETIC_DISCLAIMER
    return df


def generate_flow_csv(
    n_samples: int = 500,
    random_state: int = 42,
    attack_ratio: float = 0.3,
    missing_rate: float = 0.0,
    shift_scale: float = 1.0,
) -> Tuple[bytes, str]:
    """Return (csv_bytes, filename) for a labelled-synthetic flow dataset."""
    df = generate_flow_dataset(
        n_samples=n_samples,
        random_state=random_state,
        attack_ratio=attack_ratio,
        missing_rate=missing_rate,
        shift_scale=shift_scale,
    )
    return df.to_csv(index=False).encode("utf-8"), f"synthetic_flows_rs{random_state}.csv"
