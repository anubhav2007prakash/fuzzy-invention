# SentinelCrypt AI — Security Architecture

## Objectives
Integrity of evidence, safe input processing, controlled deployment, reproducibility, and confidentiality of local configuration.

## Controls
### Input
Schema validation; file size/type limits; safe filenames; path traversal prevention; no dynamic execution from uploads.

### Data
Separate raw datasets from generated artifacts; record checksums; avoid unnecessary sensitive data; parameterized DB operations.

### API
Restricted CORS in development; safe errors; validation; authentication/rate limiting before remote exposure.

### ML
Version preprocessing; record seeds; checksum artifacts where appropriate; separate training/inference privileges in stronger deployments.

### Audit
Canonical JSON; SHA-256 chain; verification endpoint; clearly describe detection rather than prevention.

## Secure Lifecycle
Design → threat model → implementation → unit/security tests → dependency review → controlled release.

## Logging
Do not log credentials, tokens, or unnecessary sensitive input.

## Deployment Rule
Keep the initial system local/authorized. Public deployment requires a security review.
