"""Generate dependency SBOMs and verify repository dependency manifests."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import sys
import tomllib
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_SAFE_SPDX_ID = re.compile(r"[^A-Za-z0-9.-]+")
_SPDX_TOKEN = re.compile(r"\s*(\(|\)|AND|OR|WITH|[A-Za-z0-9][A-Za-z0-9.-]*)")


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _read_requirements(path: Path) -> dict[str, str]:
    requirements: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "git+", "http:", "https:")):
            continue
        match = _REQUIREMENT_NAME.match(line)
        if not match:
            raise ValueError(f"Unsupported requirement at {path}:{line_number}: {raw_line}")
        name = _normalize_name(match.group(1))
        if name in requirements:
            raise ValueError(f"Duplicate dependency {name!r} in {path}:{line_number}")
        requirements[name] = line[match.start(1) + len(match.group(1)):].strip()
    return requirements


def _read_pyproject_dependencies(path: Path, *, include_dev: bool = True) -> dict[str, str]:
    project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
    dependencies: dict[str, str] = {}
    for requirement in project.get("dependencies", []):
        match = _REQUIREMENT_NAME.match(requirement)
        if not match:
            raise ValueError(f"Unsupported pyproject requirement: {requirement}")
        dependencies[_normalize_name(match.group(1))] = requirement[
            match.start(1) + len(match.group(1)):
        ].strip()
    dev_requirements = (
        project.get("optional-dependencies", {}).get("dev", [])
        if include_dev
        else []
    )
    for requirement in dev_requirements:
        match = _REQUIREMENT_NAME.match(requirement)
        if not match:
            raise ValueError(f"Unsupported pyproject optional requirement: {requirement}")
        name = _normalize_name(match.group(1))
        if name in dependencies:
            raise ValueError(f"Duplicate pyproject dependency {name!r}")
        dependencies[name] = requirement[match.start(1) + len(match.group(1)):].strip()
    return dependencies


def verify_manifests(
    requirements_path: Path, pyproject_path: Path, package_json_path: Path, lock_path: Path
) -> None:
    requirements = _read_requirements(requirements_path)
    pyproject = _read_pyproject_dependencies(pyproject_path)
    runtime = _read_pyproject_dependencies(pyproject_path, include_dev=False)
    if not set(runtime).issubset(requirements) or not set(requirements).issubset(pyproject):
        only_requirements = sorted(requirements.keys() - pyproject.keys())
        missing_runtime = sorted(runtime.keys() - requirements.keys())
        mismatched = sorted(
            name for name in requirements.keys() & pyproject.keys()
            if requirements[name] != pyproject[name]
        )
        raise ValueError(
            "Python dependency manifests differ: "
            f"requirements_unlisted_in_pyproject={only_requirements}, "
            f"runtime_missing_from_requirements={missing_runtime}, "
            f"specifier_mismatches={mismatched}"
        )
    mismatched = sorted(
        name for name in requirements.keys() & pyproject.keys()
        if requirements[name] != pyproject[name]
    )
    if mismatched:
        raise ValueError(f"Python dependency specifiers differ for: {mismatched}")

    package = json.loads(package_json_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("lockfileVersion") != 3:
        raise ValueError("Only npm package-lock format version 3 is supported.")
    lock_root = lock.get("packages", {}).get("")
    if not isinstance(lock_root, dict):
        raise ValueError("npm package-lock is missing its root package entry.")
    for key in ("dependencies", "devDependencies", "optionalDependencies"):
        if package.get(key, {}) != lock_root.get(key, {}):
            raise ValueError(f"frontend/package.json and package-lock.json disagree on {key}.")
    if package.get("name") != lock_root.get("name") or package.get("version") != lock_root.get("version"):
        raise ValueError("frontend/package.json and package-lock.json disagree on package identity.")


def _spdx_id(name: str, version: str, disambiguator: str = "") -> str:
    suffix = f"-{disambiguator}" if disambiguator else ""
    return "SPDXRef-" + _SAFE_SPDX_ID.sub("-", f"{name}-{version}{suffix}")


def _spdx_document(name: str, packages: list[dict[str, Any]]) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    document: dict[str, Any] = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": name,
        "documentNamespace": f"https://sentinelcrypt.invalid/sbom/{quote(name)}-{uuid4()}",
        "creationInfo": {
            "created": timestamp,
            "creators": ["Tool: sentinelcrypt-supply-chain"],
        },
        "packages": packages,
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": package["SPDXID"],
            }
            for package in packages
        ],
    }
    return document


def _distribution_license(dist: metadata.Distribution) -> tuple[str, str | None]:
    expressions = dist.metadata.get_all("License-Expression") or []
    expression = expressions[0].strip() if expressions else "NOASSERTION"
    legacy = dist.metadata.get("License")
    comment = f"Distribution metadata License: {legacy}" if legacy else None
    return expression, comment


def _npm_spdx_license(value: Any) -> tuple[str, str | None]:
    if isinstance(value, dict):
        value = value.get("type")
    if not isinstance(value, str) or not value.strip():
        return "NOASSERTION", None
    raw = value.strip()
    tokens: list[str] = []
    offset = 0
    while offset < len(raw):
        match = _SPDX_TOKEN.match(raw, offset)
        if not match:
            return "NOASSERTION", f"Unparsed package-lock license metadata: {raw}"
        tokens.append(match.group(1))
        offset = match.end()

    index = 0

    def parse_primary() -> bool:
        nonlocal index
        if index >= len(tokens):
            return False
        if tokens[index] == "(":
            index += 1
            if not parse_expression() or index >= len(tokens) or tokens[index] != ")":
                return False
            index += 1
        elif tokens[index] not in {"AND", "OR", "WITH", ")"}:
            index += 1
        else:
            return False
        if index < len(tokens) and tokens[index] == "WITH":
            index += 1
            if index >= len(tokens) or tokens[index] in {"(", ")", "AND", "OR", "WITH"}:
                return False
            index += 1
        return True

    def parse_expression() -> bool:
        nonlocal index
        if not parse_primary():
            return False
        while index < len(tokens) and tokens[index] in {"AND", "OR"}:
            index += 1
            if not parse_primary():
                return False
        return True

    if raw == "UNLICENSED" or not tokens or not parse_expression() or index != len(tokens):
        return "NOASSERTION", f"Unparsed package-lock license metadata: {raw}"
    return raw, f"License field copied from package-lock.json: {raw}"


def python_packages() -> list[dict[str, Any]]:
    installed = {
        _normalize_name(dist.metadata.get("Name", "")): dist
        for dist in metadata.distributions()
        if dist.metadata.get("Name")
    }
    requirements = _read_requirements(ROOT / "requirements.txt")
    requirements.update(_read_pyproject_dependencies(ROOT / "pyproject.toml"))
    missing = sorted(name for name in requirements if name not in installed)
    if missing:
        raise ValueError(f"Python environment is missing declared packages: {missing}")
    included = set(requirements)
    pending = list(requirements)
    while pending:
        current = pending.pop()
        dist = installed.get(current)
        if dist is None:
            continue
        for requirement in dist.requires or []:
            match = _REQUIREMENT_NAME.match(requirement)
            if not match:
                continue
            child = _normalize_name(match.group(1))
            if child in installed and child not in included:
                included.add(child)
                pending.append(child)

    packages = []
    for normalized_name in sorted(included):
        dist = installed.get(normalized_name)
        if dist is None:
            continue
        package_name = dist.metadata.get("Name", normalized_name)
        version = dist.version
        license_expression, license_comment = _distribution_license(dist)
        package: dict[str, Any] = {
            "name": package_name,
            "SPDXID": _spdx_id(package_name, version),
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": license_expression or "NOASSERTION",
            "copyrightText": "NOASSERTION",
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": f"pkg:pypi/{quote(package_name.lower())}@{quote(version)}",
                }
            ],
        }
        if license_comment:
            package["licenseComments"] = license_comment
        packages.append(package)
    return packages


def frontend_packages(lock_path: Path) -> list[dict[str, Any]]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("lockfileVersion") != 3:
        raise ValueError("Only npm package-lock format version 3 is supported.")
    packages = []
    for package_path, entry in sorted(lock.get("packages", {}).items()):
        if not package_path.startswith("node_modules/"):
            continue
        package_name = entry.get("name") or package_path.rsplit("node_modules/", 1)[-1]
        version = entry.get("version")
        if not isinstance(version, str) or not version:
            raise ValueError(f"Lock entry {package_path!r} has no resolved version.")
        valid_expression, license_comment = _npm_spdx_license(entry.get("license"))
        package: dict[str, Any] = {
            "name": package_name,
            "SPDXID": _spdx_id(
                package_name,
                version,
                hashlib.sha256(package_path.encode("utf-8")).hexdigest()[:12],
            ),
            "versionInfo": version,
            "downloadLocation": entry.get("resolved", "NOASSERTION"),
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": valid_expression,
            "copyrightText": "NOASSERTION",
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": f"pkg:npm/{quote(package_name, safe='/@')}@{quote(version)}",
                }
            ],
        }
        integrity = entry.get("integrity")
        if isinstance(integrity, str):
            package_checksums = []
            for integrity_token in integrity.split():
                if "-" not in integrity_token:
                    continue
                algorithm, digest = integrity_token.split("-", 1)
                spdx_algorithm = {
                    "sha1": "SHA1",
                    "sha256": "SHA256",
                    "sha384": "SHA384",
                    "sha512": "SHA512",
                }.get(algorithm.lower())
                if spdx_algorithm:
                    try:
                        checksum_value = base64.b64decode(digest, validate=True).hex()
                    except (binascii.Error, ValueError) as exc:
                        raise ValueError(
                            f"Invalid npm integrity value in lock entry {package_path!r}."
                        ) from exc
                    package_checksums.append(
                        {
                            "algorithm": spdx_algorithm,
                            "checksumValue": checksum_value,
                        }
                    )
            if package_checksums:
                package["checksums"] = package_checksums
        if license_comment:
            package["licenseComments"] = license_comment
        packages.append(package)
    return packages


def write_sbom(name: str, packages: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(_spdx_document(name, packages), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_checksums(paths: list[Path], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for path in sorted(paths):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.as_posix()}")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_license_inventory(sbom_paths: list[Path], output_path: Path) -> None:
    inventory: list[dict[str, Any]] = []
    for sbom_path in sbom_paths:
        document = json.loads(sbom_path.read_text(encoding="utf-8"))
        if document.get("spdxVersion") != "SPDX-2.3":
            raise ValueError(f"{sbom_path} is not an SPDX-2.3 document.")
        for package in document.get("packages", []):
            purl = next(
                (
                    reference.get("referenceLocator", "")
                    for reference in package.get("externalRefs", [])
                    if reference.get("referenceType") == "purl"
                ),
                "",
            )
            ecosystem = purl.removeprefix("pkg:").split("/", 1)[0] or "unknown"
            item: dict[str, Any] = {
                "ecosystem": ecosystem,
                "name": package["name"],
                "version": package.get("versionInfo", "NOASSERTION"),
                "license_declared": package.get("licenseDeclared", "NOASSERTION"),
            }
            if package.get("licenseComments"):
                item["license_metadata"] = package["licenseComments"]
            inventory.append(item)
    inventory.sort(key=lambda item: (item["ecosystem"], item["name"].lower(), item["version"]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "format": "sentinelcrypt-license-inventory-v1",
                "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "packages": inventory,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify", help="Verify dependency manifests and npm lock alignment.")
    verify.add_argument("--requirements", type=Path, default=ROOT / "requirements.txt")
    verify.add_argument("--pyproject", type=Path, default=ROOT / "pyproject.toml")
    verify.add_argument("--package-json", type=Path, default=ROOT / "frontend" / "package.json")
    verify.add_argument("--package-lock", type=Path, default=ROOT / "frontend" / "package-lock.json")
    python_sbom = commands.add_parser("python-sbom", help="Write an SPDX SBOM for installed Python dependencies.")
    python_sbom.add_argument("--output", type=Path, required=True)
    frontend_sbom = commands.add_parser("frontend-sbom", help="Write an SPDX SBOM from npm's lockfile.")
    frontend_sbom.add_argument("--lock", type=Path, default=ROOT / "frontend" / "package-lock.json")
    frontend_sbom.add_argument("--output", type=Path, required=True)
    checksums = commands.add_parser("checksums", help="Write SHA-256 checksums for supply-chain reports.")
    checksums.add_argument("--output", type=Path, required=True)
    checksums.add_argument("files", nargs="+", type=Path)
    licenses = commands.add_parser("licenses", help="Write a combined license inventory from SPDX SBOMs.")
    licenses.add_argument("--output", type=Path, required=True)
    licenses.add_argument("sboms", nargs="+", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "verify":
            verify_manifests(args.requirements, args.pyproject, args.package_json, args.package_lock)
            print("Dependency manifests and frontend lockfile are aligned.")
        elif args.command == "python-sbom":
            packages = python_packages()
            write_sbom("SentinelCrypt AI Python dependencies", packages, args.output)
            print(f"Wrote Python SPDX SBOM with {len(packages)} packages to {args.output}.")
        elif args.command == "frontend-sbom":
            packages = frontend_packages(args.lock)
            write_sbom("SentinelCrypt AI frontend dependencies", packages, args.output)
            print(f"Wrote frontend SPDX SBOM with {len(packages)} packages to {args.output}.")
        elif args.command == "checksums":
            write_checksums(args.files, args.output)
            print(f"Wrote SHA-256 checksums for {len(args.files)} files to {args.output}.")
        elif args.command == "licenses":
            write_license_inventory(args.sboms, args.output)
            print(f"Wrote license inventory to {args.output}.")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Supply-chain check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
