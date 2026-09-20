# SentinelCrypt AI — Vibe Coding Rules

As an AI coding agent or developer working on SentinelCrypt AI, you MUST obey these rules:

## Rule 1: Respect the Dependency Direction
- `ml/`, `xai/`, and `cryptography/` are **pure calculation modules**.
- Never import FastAPI, SQLAlchemy, or React components inside `ml/`, `xai/`, or `cryptography/`.
- All orchestration happens in `services/`.
- `api/` only handles HTTP requests, validation, and status codes.

## Rule 2: Strictly Deterministic Calculations
- Always set `random_state=42` or `seed=42` for any splitting, fitting, or perturbation.
- Canonical JSON MUST sort keys and use compact separators `(',', ':')`.

## Rule 3: No Blockchain Misnomers
- Do NOT use terms like "blockchain", "mining", "consensus", "smart contracts", or "gas".
- Use "cryptographic audit ledger", "hash chain", "canonical payload", "record hash", and "tamper verification".

## Rule 4: Follow the Phased Roadmap
- Build in this strict order:
  - Phase 1: Repo, Config, Database, Dataset Validation
  - Phase 2: Preprocessing, Models (LR, RF), Evaluator, Registry
  - Phase 3: Prediction Service & API
  - Phase 4: Cryptographic Hash Chain & Verification
  - Phase 5: SHAP & Explanation Stability
  - Phase 6: React Dashboard & Pages
  - Phase 7: Experiments EXP-A to EXP-D & Results

## Rule 5: Keep Data and Binary Artifacts out of Git
- `.pkl`, `.joblib`, `.csv`, `.parquet`, `.h5` files must stay ignored by `.gitignore`.
- Only commit code, schemas, configs, tests, and documentation.
