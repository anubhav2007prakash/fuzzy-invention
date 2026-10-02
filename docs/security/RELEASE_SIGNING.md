# Release Integrity Workflow

## Overview

The **Release Integrity Workflow** ensures that SentinelCrypt releases can be
cryptographically verified by third parties. The workflow covers the full
lifecycle from source code through build, artifact generation, signing, and
final release.

The workflow follows a **source → build → artifact → checksum → signature →
release** pipeline with established signing mechanisms and secure key management.

> **Never embed private keys in the repository.** Keys are managed exclusively
> through environment variables and hardware security modules.

## Pipeline Stages

### 1. Source

The starting point is the source code repository (Git). Every release begins
with a tagged commit that represents the exact code to be released.

#### Source Tagging

```bash
# Create an annotated tag at the release commit
git tag -a v1.0.0 -m "SentinelCrypt v1.0.0 release"

# Push the tag to the remote
git push origin v1.0.0
```

#### Source Provenance

- The git commit hash serves as the ultimate source of truth
- `git log -1 --format=%H` gives the exact commit
- `git describe --tags` resolves a tag to its commit
- All build artifacts must be reproducible from this commit

### 2. Build

The build step compiles/generates the distributable artifacts from the tagged
source. The build must be **deterministic** — the same source must always
produce the same artifacts.

#### Build Commands

```bash
# Example: Python package build
pip install build
build --sdist --wheel

# Example: Docker build
docker build -t sentinelcrypt:release .
```

#### Build Provenance

- Build timestamp: `date -u +"%Y-%m-%dT%H:%M:%SZ"`
- Build host: `hostname -f`
- Build user (non-sensitive): `whoami`
- Build environment variables (sanitized — no secrets)
- Docker image digest (if applicable): `docker images --no-trunc`

### 3. Artifact

The build produces distributable artifacts (binaries, packages, containers).

#### Artifact Types

| Type | Description |
|---|---|
| **sdist** | Source distribution (tar.gz) |
| **wheel** | Built Python wheel (.whl) |
| **Docker image** | Container image (pushed to registry) |
| **Binary** | Platform-specific executable |

#### Artifact Storage

- Artifacts are stored in a release bucket (e.g., S3, GCS, Artifactory)
- Each artifact has a unique, immutable URL
- Artifacts are never overwritten — new versions get new URLs

### 4. Checksum

Every artifact must have a cryptographic checksum (hash) for integrity verification.

#### Checksum Algorithms

- **SHA-256** (primary, recommended)
- **SHA-3-256** (alternative, optional)
- **MD5** (deprecated — do not use for new releases)

#### Generating Checksums

```bash
# SHA-256 for all artifact types
sha256sum artifact.tar.gz > SHA256SUMS
sha256sum artifact.whl >> SHA256SUMS
sha256sum sentinelcrypt-docker-image.tar | gzip > SHA256SUMS.gz
```

#### Checksum File Format (SHA-256SUMS)

```text
# SentinelCrypt v1.0.0 - SHA-256 checksums
# Generated: 2026-01-15T10:30:00Z
# Build: build-x86_64-1

3a7bd3e2360a23e335d26a2b89d17e588b2c8e13435c0e0c0f6e5c2e5b7e2e6d  sentinelcrypt-1.0.0.tar.gz
f6e29a8c9b8d7a6c5b4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1  sentinelcrypt-1.0.0-py3-none-any.whl
```

#### Verifying a Checksum

```bash
# Verify SHA-256 checksum
sha256sum -c SHA256SUMS
# Output: sentinelcrypt-1.0.0.tar.gz: OK
#         sentinelcrypt-1.0.0-py3-none-any.whl: FAILED
```

### 5. Signature

The checksum file itself is signed using established signing mechanisms. The
signature proves the checksum file's authenticity and integrity.

#### Signing Mechanisms

| Mechanism | Tool | Key Type |
|---|---|---|
| **OpenPGP (GPG)** | `gpg --sign` | RSA/ECC, 4096-bit recommended |
| **RSA-PSS** | `openssl dgst -sha256 -sign` | RSA, 4096-bit |
| **Ed25519** | `openssl dgst -sha256 -sign` | Ed25519, 256-bit |

#### Recommended: OpenPGP (GPG)

```bash
# Import the release signing public key (already trusted)
gpg --import release-signing-pubkey.asc

# Sign the checksums file
gpg --armor --detach-sign SHA256SUMS

# Result: SHA256SUMS.sig (ASCII-armored detached signature)
```

#### Verifying a Signature

```bash
# Import the public key if not already trusted
gpg --keyserver hkps://keyserver.ubuntu.com --recv-keys <key-id>

# Verify the signature
gpg --verify SHA256SUMS.sig SHA256SUMS

# Output example:
# gpg: Signature made 2026-01-15 10:30:00 using RSA key AAAABBBBCCCCDDDD...
# gpg: Good signature from "SentinelCrypt Release <release@sentinelcrypt.ai>"
```

#### RSA-PSS Signing (OpenSSL)

```bash
# Sign the checksums file
openssl dgst -sha256 -sign release-key.pem -out SHA256SUMS.sig SHA256SUMS

# Verify the signature
openssl dgst -sha256 -verify public-key.pem -signature SHA256SUMS.sig SHA256SUMS
```

### 6. Release

The final step is publishing the artifacts, checksums, and signatures together.

#### Release Assets

Each release package includes:

| Asset | Description |
|---|---|
| **Artifact** | The actual distributable (wheel, sdist, Docker tarball) |
| **SHA256SUMS** | Checksum file with hashes for all assets |
| **SHA256SUMS.sig** | Cryptographic signature of the checksums |
| **Release Notes** | Human-readable changes, migration guide, known issues |
| **SBOM** (Software Bill of Materials) | Dependency inventory in SPDX format |

#### Publishing Example (GitHub Release)

```bash
# Create a GitHub release
gh release create v1.0.0 \
  --title "SentinelCrypt v1.0.0" \
  --notes "$(cat CHANGELOG.md)" \
  --generate-notes \
  sentinelcrypt-1.0.0.tar.gz \
  sentinelcrypt-1.0.0-py3-none-any.whl \
  SHA256SUMS \
  SHA256SUMS.sig
```

## Key Management

### Never Embed Private Keys in Repository

Private keys **must never** be committed to the Git repository, even in encrypted
form or version-controlled secrets files. The repository contains only:

- Public keys (for verification)
- Configuration describing key IDs and keygrip identifiers
- Build scripts that reference environment variables

#### What Not to Commit

```text
❌ Private GPG keys (.asc, .private.asc)
❌ RSA private keys (pem, key files)
❌ Secret signing tokens
❌ Passwords and passphrases
❌ Environment variable values containing secrets
```

#### What Should Be Committed

```text
✅ Public GPG keys (.asc - signed by the key owner)
✅ Public RSA keys (for verification only)
✅ Key IDs and fingerprints
✅ Build configuration templates (without secret values)
✅ Dockerfiles and build scripts
✅ CI/CD configuration (referencing secrets via env vars)
```

### Secure Key Management

#### GPG Key Lifecycle

```text
Key Generation → Key Signing → Key Upload → Key Usage → Key Retirement → Key Revocation
```

**Key Generation** (performed once by the release manager):

```bash
# Generate a new GPG key for release signing
gpg --full-generate-key

# Key features:
# - RSA (4096 bits) or Ed25519
# - Valid for 2 years (renewal required)
# - Real name: "SentinelCrypt Release"
# - Email: release@sentinelcrypt.ai
# - Comment: "Release signing key - never used for email encryption"

# Export the public key (commit to repo)
gpg --armor --export release@sentinelcrypt.ai > release-signing-pubkey.asc

# Export the private key ONLY to a secure offline location (NOT the repo)
# Store on hardware security module or encrypted USB drive
```

**Key Storage Options** (ranked by security):

| Option | Description | Risk Level |
|---|---|---|
| **Hardware Security Module (HSM)** | Dedicated hardware for key operations | 🔒 Best |
| **GPG smartcard + PIN** | YubiKey or similar with PIV | 🔒 Very Good |
| **Air-gapped workstation** | Dedicated machine, never network-connected | 🔒 Good |
| **Encrypted environment variable** | `GPG_PRIVATE_KEY_BASE64` in CI secrets | 🟡 Acceptable (CI only) |
| **HashiCorp Vault** | Managed secrets with audit logging | 🟡 Acceptable (audited) |

**Key Rotation**:

- Rotate release signing keys every 2 years
- Old keys remain valid for verification of existing releases
- New keys signed by old keys during transition period
- Document key transition in release notes

#### CI/CD Integration

The CI/CD pipeline signs releases without ever exposing private keys:

```yaml
# Example: GitHub Actions workflow step
- name: Sign release checksums
  env:
    GPG_TTY: ${{ github.exec_path }}
    GPG_PRIVATE_KEY_BASE64: ${{ secrets.GPG_PRIVATE_KEY_BASE64 }}
  run: |
    echo "$GPG_PRIVATE_KEY_BASE64" | gpg --batch --import
    gpg --armor --detach-sign SHA256SUMS
    # Upload signature as release asset
```

#### Verification in CI

```yaml
- name: Verify release signature
  env:
    GPG_TTY: ${{ github.exec_path }}
  run: |
    gpg --verify SHA256SUMS.sig SHA256SUMS
    # Fail the workflow if verification fails
    if [ $? -ne 0 ]; then
      echo "Release signature verification FAILED"
      exit 1
    fi
    echo "Release signature verification PASSED"
```

## Third-Party Verification Instructions

### For End Users

```bash
# 1. Download the release assets
wget https://example.com/releases/v1.0.0/sentinelcrypt-1.0.0.tar.gz
wget https://example.com/releases/v1.0.0/SHA256SUMS
wget https://example.com/releases/v1.0.0/SHA256SUMS.sig

# 2. Verify the checksum
sha256sum -c SHA256SUMS

# 3. Verify the signature (using the public key)
gpg --verify SHA256SUMS.sig SHA256SUMS

# 4. If both pass, the release is authentic and untampered
```

### For Package Managers

```bash
# Verify before installation
gpg --verify SHA256SUMS.sig SHA256SUMS

# Check the checksum matches the downloaded artifact
sha256sum sentinelcrypt-1.0.0.tar.gz

# Both must pass for the package to be considered authentic
```

### For Security Auditors

1. **Confirm the public key** is the expected one (compare fingerprints)
2. **Verify the signature chain** from the signature to the trusted public key
3. **Check the checksums** verify all artifacts
4. **Review the release notes** for any known issues or migration steps
5. **Verify the SBOM** matches the actual dependencies

## Test Keys (For Development Only)

**Never use test keys for production releases.** Test keys are for development
and CI/CD pipeline testing only.

### Generating Test Keys

```bash
# Generate a test GPG key (no real-name requirements)
gpg --full-generate-key
# Select option for RSA (sign only)
# Key size: 2048 bits (test only)
# Validity: 1 year (test only)
# Name: "Test Release Key"
# Email: test@localhost

# Export test public key
gpg --armor --export "Test Release Key" > test-signing-pubkey.asc

# Export test private key (for CI only, never production)
gpg --armor --export-secret-keys "Test Release Key" > test-signing-privkey.asc
```

### Test Verification Workflow

```bash
# Create test artifacts
echo "test" > test-artifact.tar.gz
sha256sum test-artifact.tar.gz > test-SHA256SUMS
gpg --batch --default-key "Test Release Key" --armor --detach-sign test-SHA256SUMS

# Test verification
gpg --verify test-SHA256SUMS.sig test-SHA256SUMS
sha256sum -c test-SHA256SUMS
```

Both commands should output "Good signature" and "OK" respectively.

### Test Key Fingerprint (Share Publicly)

```
gpg --keyid-format LONG --fingerprint "Test Release Key"
```

Share the fingerprint through a trusted channel so downstream verifiers can
import the correct public key.

## Security Considerations

### Replay Protection

- Each release has a unique version number
- Checksum files include the build timestamp
- Signatures are version-specific
- Old signatures do not validate against new release versions

### Compromise Response

If a signing key is compromised:

1. **Immediately revoke** the compromised key
   ```bash
   gpg --output revocation-certificate.asc --gen-revoke key-id
   ```
2. **Publish the revocation** to key servers
3. **Release a new version** signed with a new key
4. **Notify all consumers** to verify with the new key
5. **Audit all previous releases** signed with the compromised key

### Attack Mitigation

- **Timestamp attacks**: Signatures include creation time; old signatures become invalid for new releases
- **Key theft**: Hardware storage (HSM, smartcard) prevents remote key extraction
- **Checksum tampering**: Separate signature of checksum file ensures checksum integrity
- **Man-in-the-middle**: Use HTTPS for all downloads; GPG signature provides additional layer

## Compliance & Standards

This workflow aligns with:

- **RFC 4880** — OpenPGP message format
- **NIST SP 800-57** — Key management guidelines
- **ISO 27001** — Information security management
- **CIS Benchmarks** — Secure configuration standards
- **SWID Tag** — Software identification for inventory management

## Frequently Asked Questions

### Q: Can I use a different signing mechanism?

A: Yes, but OpenPGP (GPG) is the recommended and most widely supported method.
Other mechanisms (RSA-PSS, Ed25519) are acceptable if they provide equivalent
security and verification capabilities.

### Q: How do I verify a release without GPG?

A: You can use OpenSSL for RSA-PSS verification:

```bash
openssl dgst -sha256 -verify public-key.pem -signature SHA256SUMS.sig SHA256SUMS
```

But GPG is the recommended and fully supported method.

### Q: What if someone modifies an artifact after signing?

A: The checksum will not match, and `sha256sum -c SHA256SUMS` will report
"FAILED". The signature verification will also fail because the checksum file
itself would have a different hash.

### Q: How do I handle multiple architectures/platforms?

A: Include all artifacts in the same release, each with its own line in
SHA256SUMS. The signature covers the entire SHA256SUMS file, verifying all
artifacts at once.

### Q: Can I automate the entire workflow?

A: Yes. The CI/CD pipeline can handle building, checksumming, and signing
automatically. The key setup (importing, trust) must be done manually once by
the release manager.