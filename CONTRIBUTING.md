# Contributing to SentinelCrypt AI

First off — thank you for taking the time to contribute! 🎉

SentinelCrypt AI is a research-oriented network intrusion detection platform
combining machine learning, explainable AI, and cryptographic evidence
verification. Every improvement — whether it's a bug fix, a new test, better
documentation, or a new experiment — makes the research stronger.

Please read this guide before opening a pull request. It helps maintainers
review contributions quickly and keeps the codebase coherent.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [How to Report a Bug](#how-to-report-a-bug)
3. [How to Request a Feature](#how-to-request-a-feature)
4. [Development Setup](#development-setup)
5. [Project Structure](#project-structure)
6. [Branch & Commit Conventions](#branch--commit-conventions)
7. [Pull Request Process](#pull-request-process)
8. [Testing Requirements](#testing-requirements)
9. [Code Style](#code-style)
10. [Research Integrity Requirements](#research-integrity-requirements)
11. [Security Contributions](#security-contributions)

---

## Code of Conduct

This project follows our [Code of Conduct](CODE_OF_CONDUCT.md). By
participating you agree to uphold it. Please report unacceptable behaviour via
GitHub Security Advisories or a private issue.

---

## How to Report a Bug

Before opening a new issue, please search existing issues to avoid duplicates.

When reporting a bug, include:

- **Short descriptive title**
- **Steps to reproduce** (minimal reproducible example preferred)
- **Expected behaviour** vs **actual behaviour**
- **Environment:** OS, Python version, Node.js version, browser (if frontend)
- **Relevant logs or tracebacks** (redact any sensitive data)
- **Branch / commit hash** where the bug was observed

Open a bug report at:
<https://github.com/anubhav2007prakash/fuzzy-invention/issues/new?template=bug_report.md>

---

## How to Request a Feature

Feature requests are welcome! Please describe:

- **The problem you're trying to solve** (not just the solution)
- **Proposed solution or API** (optional — we can design it together)
- **Alternatives considered**
- **Relevance to the research goals** of SentinelCrypt AI

Open a feature request at:
<https://github.com/anubhav2007prakash/fuzzy-invention/issues/new?template=feature_request.md>

---

## Development Setup

### Prerequisites

| Tool | Minimum version |
|------|----------------|
| Python | 3.10 |
| Node.js | 18 |
| npm | 9 |
| Git | 2.40 |

### 1. Fork and clone

```bash
git clone https://github.com/<your-username>/fuzzy-invention.git
cd fuzzy-invention
```

### 2. Backend environment

```bash
# Create and activate a virtual environment
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Install all dependencies including dev extras
pip install -r requirements.txt
pip install -e ".[dev]"
```

### 3. Frontend environment

```bash
cd frontend
npm ci          # install exact versions from package-lock.json
npm run dev     # start Vite dev server at http://localhost:5173
```

### 4. Backend dev server

```bash
# From the repo root, with the virtual environment active
uvicorn backend.app.main:app --reload --port 8000
```

### 5. Verify your setup

```bash
# Backend tests
python -m pytest backend/tests -v

# Frontend tests
cd frontend && npm test
```

All tests must pass before submitting a PR.

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routers (v1)
│   │   ├── core/          # Config, logging, exception handlers
│   │   ├── cryptography/  # SHA-256 hash chain, canonicalization, verifier
│   │   ├── db/            # SQLAlchemy ORM models & repositories
│   │   ├── ml/            # Preprocessing, classifiers, metrics
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── services/      # Business logic orchestration
│   │   └── xai/           # SHAP explainer & stability evaluation
│   └── tests/
│       ├── failure_injection/   # Controlled failure injection framework
│       ├── integration/         # End-to-end API tests
│       ├── metamorphic/         # Metamorphic relation tests
│       └── unit/                # Fast, isolated unit tests
├── frontend/
│   └── src/
│       ├── api/           # REST client functions
│       ├── components/    # Reusable React components
│       └── pages/         # Route-level pages
├── docs/                  # Architecture & research documentation
├── scripts/               # CLI utilities (supply chain, experiments)
└── .github/workflows/     # CI/CD pipelines
```

---

## Branch & Commit Conventions

### Branches

| Pattern | Purpose |
|---------|---------|
| `main` | Stable, passing all CI checks |
| `feat/<short-name>` | New features |
| `fix/<short-name>` | Bug fixes |
| `docs/<short-name>` | Documentation only |
| `test/<short-name>` | Tests only |
| `chore/<short-name>` | Maintenance (deps, CI, tooling) |

Always branch off `main`:

```bash
git checkout main && git pull
git checkout -b feat/my-feature
```

### Commit messages

We follow **Conventional Commits** (<https://www.conventionalcommits.org/>):

```
<type>(<scope>): <short imperative summary>

[optional body — wrap at 72 chars]

[optional footer: Breaking changes, closes #issue]
```

**Types:** `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `perf`, `ci`

**Examples:**
```
feat(xai): add SHAP stability score to explanation API response
fix(cryptography): prevent hash chain gap on concurrent audit writes
test(failure-injection): add missing-config injector lifecycle test
docs(readme): update dataset acquisition section for CICIDS2017
```

---

## Pull Request Process

1. **Open a draft PR early** — don't wait until everything is perfect.
2. **Fill out the PR template** completely.
3. Ensure the following before marking ready for review:
   - [ ] All existing tests pass (`pytest backend/tests -v`)
   - [ ] New code has tests (see [Testing Requirements](#testing-requirements))
   - [ ] Linting passes (`ruff check .` / `eslint frontend/src`)
   - [ ] Commit messages follow Conventional Commits
   - [ ] Documentation updated if behaviour changed
   - [ ] No secrets, credentials, `.env` files, or private keys committed
4. Request a review from at least one maintainer.
5. Address review comments; maintainers will merge once approved.

### What we look for in reviews

- Correctness and test coverage
- Research integrity (no data leakage, unbiased evaluation)
- Cryptographic correctness (hash chain invariants preserved)
- No regressions to existing experiments
- Clear, readable code and comments

---

## Testing Requirements

### Minimum coverage requirements

| Area | Requirement |
|------|------------|
| New service functions | Unit test + at least one integration test |
| New API endpoints | Integration test via `httpx.AsyncClient` |
| New cryptography code | Unit test verifying hash chain invariants |
| Failure injection injectors | Lifecycle test: activate → inject → revert |
| ML preprocessing | Test for data-leakage absence |

### Running specific test suites

```bash
# All unit tests
python -m pytest backend/tests/unit -v

# Integration tests
python -m pytest backend/tests/integration -v

# Failure injection framework tests
python -m pytest backend/tests/unit/test_failure_injection_framework.py -v

# Chaos failure tests
python -m pytest backend/tests/unit/test_chaos_failures.py -v

# Frontend tests
cd frontend && npm test
```

### Test isolation rules

- Unit tests **must not** make network calls or touch real databases.
- Use SQLite in-memory (`sqlite:///:memory:`) for database fixtures.
- Use `pytest` fixtures and `unittest.mock` for external dependencies.
- The failure injection framework (`backend/tests/failure_injection/`)
  **must always revert** injected faults — verify with `assert_consistent_state`.

---

## Code Style

### Python

- Formatter: [`ruff format`](https://docs.astral.sh/ruff/) (line length 88)
- Linter: [`ruff check`](https://docs.astral.sh/ruff/)
- Type hints required on all public functions and methods
- Docstrings on all public classes and functions (Google style)

```bash
ruff format .
ruff check .
```

### JavaScript / JSX

- Formatter: [Prettier](https://prettier.io/) (configured in `package.json`)
- Linter: [ESLint](https://eslint.org/)

```bash
cd frontend
npm run lint
```

### General

- No commented-out dead code in committed files
- No `print()` debug statements (use the configured `logging` module)
- Keep functions short and single-purpose
- Prefer explicit over implicit

---

## Research Integrity Requirements

SentinelCrypt AI is a scientific research platform. The following rules are
**non-negotiable** for any code touching the ML pipeline or experiments:

1. **No data leakage.** Preprocessing scalers and encoders must be fitted
   exclusively on the training split. Never call `.fit()` on validation/test
   data.
2. **Reproducible results.** All experiments must set `random_state=42`
   (or a documented seed) and record it in result metadata.
3. **Honest metrics.** Report macro/weighted Precision, Recall, F1, FPR,
   and PR-AUC. Do not cherry-pick metrics to make results look better.
4. **Hash chain invariants.** Never write code that skips, modifies, or
   deletes existing audit records. The ledger is append-only.
5. **Experiment result files are read-only.** Results stored under `results/`
   are evidence artifacts. Never auto-overwrite them without creating a new
   timestamped file.
6. **Cite your sources.** If you implement an algorithm from a paper, add the
   citation to the docstring and to `docs/research/`.

---

## Security Contributions

If you find a security vulnerability, **do not open a public issue**.

Please report it privately via:
- [GitHub Security Advisory](https://github.com/anubhav2007prakash/fuzzy-invention/security/advisories/new)

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes (optional)

We will respond within **72 hours** and aim to release a fix within **14 days**
for confirmed vulnerabilities.

See [SECURITY.md](SECURITY.md) for the full security policy.

---

Thank you for contributing to SentinelCrypt AI! 🚀
