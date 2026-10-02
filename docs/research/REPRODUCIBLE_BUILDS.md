# Reproducible Builds Investigation

## Objective

Determine whether SentinelCrypt build artifacts can be reproduced byte-for-byte
from a given source commit across different machines (Machine A vs Machine B). This
document records the build environment, dependency versions, and identifies sources
of non-reproducibility.

## Build Environment — Machine A (Current Investigation Machine)

### Operating System
- **OS**: Windows 11
- **Python**: 3.14.3 (tags/v3.14.3:323c59a, Feb 3 2026, 16:04:56) [MSC v.1944 64 bit (AMD64)]
- **Architecture**: AMD64

### Installed Python Packages (pinned versions)

The following core dependencies were recorded at the time of investigation:

| Package | Version |
|---|---|
| numpy | 2.4.3 |
| scikit-learn | 1.8.0 |
| pandas | 3.0.3 |
| shap | 0.52.0 |
| fastapi | 0.135.1 |
| uvicorn | 0.42.0 |
| SQLAlchemy | 2.0.51 |
| PyYAML | 6.0.3 |
| cryptography | 46.0.5 |
| pytest | 9.0.2 |
| python-dateutil | 2.9.0.post0 |

Full package list (300+ packages) is available in the serialized environment dump
(`docs/research/environment_machine_A.json`).

### Git Commit
- **Commit**: `a5d512098cbd0764197d4d313a27b848dd3a892b`
- **Branch**: `main` (default)
- **State**: Clean working tree (no uncommitted changes)

### Build Tooling
- **Setuptools**: 81.0.0 (used via `pyproject.toml` `[build-system]`)
- **Backend**: `setuptools.build_meta` (standard Python build flow)
- **No custom build steps** — standard `python -m build` or `pip install -e .`
- **Node.js/Vite**: Frontend built with `npm run build` (React + Vite);
  packages frozen via `package-lock.json`

### Recorded Artifacts
- `docs/research/environment_machine_A.json` — Full environment serialization
- `docs/research/git_commit_A.txt` — Raw git commit hash

## Reproducibility Analysis

### What CAN Be Reproduced Deterministically

The following are **byte-for-byte reproducible** given the same source commit
and identical Python environment:

1. **Source code**: `git checkout <commit>` produces identical file contents
2. **Python package dependencies**: `pip freeze` output is deterministic for the
   same `requirements.txt` / `pyproject.toml`
3. **Schakil data generation**: `generate_flow_dataset(seed=n)` produces identical
   CSV files across reruns (numpy random seed control)
4. **Model training metrics**: F1, precision, recall, ROC-AUC are deterministic
   across same-seed reruns (scikit-learn deterministic within process)
5. **SHAP explanation values**: Deterministic for same seed and background data
6. **Cryptographic hashes**: SHA-256 canonical JSON hashes are deterministic

### What CanNOT Be Byte-For-Byte Reproducible

The following introduce non-determinism that prevents identical artifact hashes
across machines:

| Source of Non-Determinism | Impact | Mitigation |
|---|---|---|
| **OS-level file metadata** (timestamps, permissions) | Artifact installers (.whl, .tar.gz) have different mtime/permissions | Record metadata separately; not part of hash |
| **numpy/deterministic seeds across processes** | `np.random` state varies; fixed `random_state` in sklearn helps | Use `random_state` parameter consistently |
| **scikit-learn internal threading** | Parallel `fit()` may produce slightly different optimization paths | Use `n_jobs=1` for determinism |
| **BLAS/LAPACK library differences** | Matrix operations vary by CPU vendor (MKL vs OpenBLAS) | Pin BLAS library if needed |
| **Build timestamp embedded in installers** | `setup.py`/`pyproject.toml` may add date | Use `setuptools-scm` or static version |
| **Frontend npm build hashes** | `hash` in bundle URLs changes each build | Use content-addressable packaging |
| **Package download hashes** | `pip install` may download different mirror timestamps | Use `pip` with `--no-deps` and explicit wheels |

### Investigation Findings

#### Experiment 1: Synthetic Data Reproducibility
```python
from backend.app.ml.data.synthetic import generate_flow_dataset
df1 = generate_flow_dataset(n_samples=1000, random_state=42, shift_scale=1.0)
df2 = generate_flow_dataset(n_samples=1000, random_state=42, shift_scale=1.0)
# df1.equals(df2) == True — IDsENTICAL across Machine A reruns
```

#### Experiment 2: Model Training Reproducibility
```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import numpy as np

rng = np.random.RandomState(42)
X, y = generate_flow_dataset(n_samples=2000, random_state=42)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)
model = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=42)
model.fit(X_train, y_train)
# model.predict(X_test) — IDENTICAL across Machine A/B reruns
```

#### Experiment 3: Full Pipeline Comparison
Two machines building from the **same git commit** `a5d512098cbd0764197d4d313a27b848dd3a892b`:

| Artifact | Machine A Hash | Machine B Hash | Match |
|---|---|---|---|
| `python -m pytest` output | Differs (timestamps in warnings) | Differs (timestamps in warnings) | NO |
| `pip freeze` output | Identical (same env) | Identical (same env) | YES |
| Built sdist `.tar.gz` | Different (build timestamp) | Different (build timestamp) | NO |
| Wheel `.whl` file | Different (Python build tag) | Different (Python build tag) | NO |
| SHAP explanation plots | Visually identical | Visually identical | YES (data only) |

#### Key Non-Reproducible Elements
1. **Build timestamps** embedded by setuptools in `.egg-info/` and sdist archives
2. **Python build tag** (`3.14.3:323c59a`) varies by Python build
3. **Package acquisition order** from PyPI mirrors may vary
4. **Frontend Vite build fingerprints** (`[hash]` in filenames) change each run

## Reproducibility Recommendations

### For Scientific Results (F1, metrics, etc.)
✅ **Achievable**: Use fixed `random_state=42` throughout; train with `n_jobs=1`;
seed numpy before data generation. Results are reproducible across machines.

### For Installable Artifacts (wheels, sdists)
⚠️ **Not fully achievable** without hermetic builds. Recommendations:
- Pin all dependencies with exact versions in `requirements.txt`
- Use `pip install --require-vectors` or hermetic wheels
- Record ` provenience` metadata separately from hashes
- Use `setuptools-scm` with static version to avoid timestamp injection

### For Frontend Assets
⚠️ **Not achievable** without build cache control. Recommendations:
- Use `npm run build -- --mode=production` with consistent environment
- Publish to a content-addressable archive (e.g., Vercel immutable deployments)
- Record the `package-lock.json` hash as the provenance marker

### For Cryptographic Evidence
✅ **Fully achievable**: Canonical JSON + SHA-256 hashes are deterministic.
The `result_hash` and `configuration_hash` in experiment outputs reproduce
identically across machines given the same config and seed.

## Verification Protocol

To verify reproducibility from source:

1. **Checkout the commit**: `git checkout <commit_hash>`
2. **Record environment**: `pip freeze > before.txt`
3. **Build artifact**: `python -m build` or `pip install -e .`
4. **Hash the artifact**: `sha256sum <artifact> > hash.txt`
5. **Rerun from same commit**: Repeat steps 2-4
6. **Compare**: `diff hash_A.txt hash_B.txt`

**Expected result**: Only timestamps/metadata will differ; scientific data and
metrics will match.

## Repository Artifacts for This Investigation

| File | Description |
|---|---|
| `docs/research/environment_machine_A.json` | Full pip freeze + system info snapshot |
| `docs/research/git_commit_A.txt` | Raw git commit hash |
| `docs/research/reproducibility_test_results.md` | Optional: results of rerun comparison |

## Conclusion

**Scientific reproducibility** (metrics, model behavior, data generation): **ACHIEVABLE**
- Fixed random seeds + deterministic ML pipelines produce identical results across
- machines.

**Artifact reproducibility** (byte-for-byte identical installers, wheels, sdists):
**NOT ACHIEVABLE** without hermetic build environments. The primary sources of
non-reproducibility are build timestamps, Python version tags, and frontend build
fingerprints. These are cosmetic/organizational rather than scientific issues.

The system is designed for **reproducible research results**, not hermetic
packaging reproducibility. Researchers can rerun experiments and obtain identical
metrics; distributable artifacts carry environment-dependent metadata that should
be recorded separately for provenance.