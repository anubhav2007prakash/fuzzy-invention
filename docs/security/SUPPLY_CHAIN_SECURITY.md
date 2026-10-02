# Software Supply-Chain Security

SentinelCrypt's supply-chain workflow inventories dependencies, checks the
frontend lockfile, scans dependencies and Git history, and emits checksummed
SBOM reports. The workflow is defined in
[`.github/workflows/supply-chain.yml`](../../.github/workflows/supply-chain.yml).

## Checks performed

| Area | CI check | Output / policy |
| --- | --- | --- |
| Python dependency inventory | `scripts/supply_chain.py python-sbom` over an isolated environment installed from `requirements.txt` | SPDX 2.3 JSON, including resolved installed package versions, PyPI package URLs, and declared license metadata when available |
| Frontend dependency inventory | `npm ci --ignore-scripts` and `scripts/supply_chain.py frontend-sbom` using `frontend/package-lock.json` | SPDX 2.3 JSON with resolved package versions, npm package URLs, lockfile integrity digests, and license metadata |
| Manifest consistency | `scripts/supply_chain.py verify` | Ensures every Python runtime dependency appears with the same specifier in `requirements.txt`, checks overlapping development dependencies for drift, and verifies frontend dependency declarations against the package-lock root |
| Frontend lock verification | `npm ci` | Fails if the checked-in npm lockfile cannot install consistently with the package manifest or its integrity data |
| Python vulnerability scanning | Pinned `pip-audit` CLI against the isolated Python environment built from `requirements.txt` and `.[dev]` | Fails on reported vulnerabilities and unsupported/unresolved packages |
| Frontend vulnerability scanning | `npm audit --audit-level=high` | Fails on high- or critical-severity advisories |
| Secret scanning | Pinned Gitleaks CLI over the full Git history | Fails on detected secrets; output is redacted |
| Dependency license inventory | `scripts/supply_chain.py licenses` over both SPDX files | JSON inventory of package name, ecosystem, version, declared license, and source metadata |
| Report integrity | `scripts/supply_chain.py checksums` | SHA-256 `SHA256SUMS` for generated SBOM and license inventory reports |

The workflow has read-only repository permissions and pins its GitHub Actions
to commit SHAs. Reports are uploaded as a 30-day Actions artifact even when a
scan fails, when at least one SBOM was generated.

## Python lockfile status

The repository currently has **no Python resolver lockfile**. Its Python
dependencies use version ranges in `requirements.txt` and `pyproject.toml`.
CI verifies that those two declarations agree, resolves them in a clean virtual
environment, runs `pip check`, scans the declared dependency graph, and records
the resolved environment in the Python SBOM. These measures do **not** make
Python installs reproducible: package resolution may vary over time and the
workflow does not claim that Python dependencies are locked or hash-pinned.

`frontend/package-lock.json` is the only checked-in dependency lockfile today.
`npm ci` verifies it against the frontend manifest and uses its resolved
versions and integrity values. Runtime dependency installation scripts are
disabled in CI using `--ignore-scripts`.

## License inventory

The SBOM package entries carry the license expression when a package provides
one. Python legacy `License` metadata is preserved as a comment and is not
automatically promoted to an SPDX license expression. Missing or
non-machine-readable values are represented as `NOASSERTION`; this is not a
license approval. Review notices, transitive obligations, and package-specific
license terms before distribution.

## Running locally

From the repository root:

```powershell
python scripts/supply_chain.py verify
npm ci --ignore-scripts --prefix frontend
python -m venv .venv-supply-chain
.\.venv-supply-chain\Scripts\python.exe -m pip install -r requirements.txt ".[dev]" pip-audit==2.9.0
.\.venv-supply-chain\Scripts\python.exe scripts/supply_chain.py python-sbom --output artifacts/supply-chain/python-sbom.spdx.json
python scripts/supply_chain.py frontend-sbom --output artifacts/supply-chain/frontend-sbom.spdx.json
python scripts/supply_chain.py licenses --output artifacts/supply-chain/license-inventory.json artifacts/supply-chain/python-sbom.spdx.json artifacts/supply-chain/frontend-sbom.spdx.json
.venv-supply-chain\Scripts\pip-audit.exe --strict
npm audit --prefix frontend --audit-level=high
gitleaks detect --source . --redact --verbose
python scripts/supply_chain.py checksums --output artifacts/supply-chain/SHA256SUMS artifacts/supply-chain/python-sbom.spdx.json artifacts/supply-chain/frontend-sbom.spdx.json artifacts/supply-chain/license-inventory.json
```

Verify generated report checksums with:

```powershell
$root = (Get-Location).Path
Get-Content artifacts/supply-chain/SHA256SUMS | ForEach-Object {
  $expected, $relativePath = $_ -split '\s+', 2
  $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $root $relativePath.Trim())).Hash
  if ($actual -ne $expected) { throw "Checksum mismatch: $relativePath" }
}
```

On a system with `sha256sum`, use `sha256sum -c artifacts/supply-chain/SHA256SUMS`.
The checksums establish whether these report files changed relative to that
checksum list; they do not authenticate the list or prove who generated the
reports.

## Interpreting scan results

An empty vulnerability report only means the configured scanner found no
matching advisory in its current data for the dependency versions it resolved.
It is not evidence that a dependency is secure, free of undisclosed flaws,
maintained, correctly configured, or safe for SentinelCrypt's use. Advisory
databases have coverage and publication delays; evaluate dependency provenance,
maintenance, transitive behavior, and the application's exposure as well.

SBOMs are inventories, not attestations or security certifications. The Python
SBOM describes the environment resolved during that workflow run; because
Python is not locked, later runs can describe different versions. npm package
integrity values come from the committed npm lockfile. SHA-256 report
checksums do not make the reports tamper-proof when stored beside them.

## GitHub documentation

- [GitHub Actions secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)
- [GitHub artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations)

An attestation can help establish where and how a release artifact was built,
but GitHub also notes that attestations do not guarantee artifact security.
This workflow generates SBOMs and scans; it does not yet publish or verify
release attestations.

The local Gitleaks command assumes `gitleaks` is installed.
