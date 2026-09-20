# SentinelCrypt AI — README & Developer Guide

## Overview
A defensive research prototype combining ML intrusion detection, explainability, and tamper-evident evidence.

## Quick Start
1. Create Python virtual environment.
2. Install pinned dependencies.
3. Configure local environment.
4. Register approved dataset.
5. Run preprocessing/training.
6. Start FastAPI.
7. Start React frontend.
8. Run tests.

Add exact commands after implementation so documentation matches the real repository.

## Structure
```text
app/          application
tests/        tests
notebooks/    experiments
frontend/     React
docs/         documentation
data/         ignored local datasets
artifacts/    generated outputs
```

## Development Rules
Never commit secrets or restricted datasets. Test security-critical code. Record experiment configuration.

## Reproducibility
Every result should reference dataset hash, code commit, configuration, seed, and environment.

## Troubleshooting
Document actual observed issues and verified solutions after implementation.
