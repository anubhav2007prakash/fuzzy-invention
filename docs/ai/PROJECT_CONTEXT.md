# SentinelCrypt AI — AI Project Context

## Purpose & Mission
SentinelCrypt AI is a verifiable Machine Learning framework for Network Intrusion Detection Systems (NIDS). It integrates explainability (SHAP), evidence generation (canonical JSON), and cryptographic auditability (forward-linked SHA-256 hash chains) to enable tamper-evident threat detection.

## Key Principles
1. **Verifiable ML:** Every prediction is paired with a verifiable evidence packet and an immutable cryptographic audit record.
2. **Deterministic Processing:** Reproducible random seeds (`seed=42`), standardized RFC 8785 canonical JSON sorting, and deterministic hashing.
3. **Strict Layer Isolation:** Pure ML/XAI/Crypto algorithms have zero awareness of HTTP, ORM, or UI layers.
4. **Research-Driven:** Rigorous experimental validation across cross-dataset generalization (EXP-A), explanation stability (EXP-B), ledger integrity (EXP-C), and model comparison (EXP-D).
5. **No Blockchain Jargon:** Strictly refer to the data integrity mechanism as an append-only cryptographic hash chain or audit ledger.
