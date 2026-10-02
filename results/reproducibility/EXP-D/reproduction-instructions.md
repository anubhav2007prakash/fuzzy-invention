# Reproducing EXP-D

1. Clone the repository at the commit recorded in `environment.json` (`git.commit`).
2. Install pinned packages from `environment.json` (`packages`).
3. `alembic upgrade head`
4. `python scripts/sentinel.py experiment run EXP-D` with the configuration in `config.yaml`.
5. Compare your `results.json` `result_hash` against the recorded value; identical canonical hashes indicate a bit-reproducible run.
