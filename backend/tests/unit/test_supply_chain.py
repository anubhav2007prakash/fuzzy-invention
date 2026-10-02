from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
import shutil
from pathlib import Path

from scripts.supply_chain import (
    frontend_packages,
    _npm_spdx_license,
    verify_manifests,
    write_checksums,
    write_license_inventory,
    write_sbom,
)

ROOT = Path(__file__).resolve().parents[3]


class SupplyChainTests(unittest.TestCase):
    def test_repository_dependency_manifests_are_consistent(self):
        verify_manifests(
            ROOT / "requirements.txt",
            ROOT / "pyproject.toml",
            ROOT / "frontend" / "package.json",
            ROOT / "frontend" / "package-lock.json",
        )

    def test_frontend_manifest_lock_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "backend" / "tests") as temp_dir:
            folder = Path(temp_dir)
            package_json = folder / "package.json"
            package_lock = folder / "package-lock.json"
            shutil.copyfile(ROOT / "frontend" / "package.json", package_json)
            lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
            lock["packages"][""]["dependencies"]["react"] = "^0.0.1"
            package_lock.write_text(json.dumps(lock), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "disagree on dependencies"):
                verify_manifests(
                    ROOT / "requirements.txt",
                    ROOT / "pyproject.toml",
                    package_json,
                    package_lock,
                )

    def test_frontend_sbom_contains_resolved_versions_licenses_and_integrity(self):
        packages = frontend_packages(ROOT / "frontend" / "package-lock.json")
        self.assertTrue(packages)
        self.assertTrue(all(package["versionInfo"] for package in packages))
        self.assertTrue(all(package["licenseDeclared"] for package in packages))
        self.assertTrue(all(package["SPDXID"] for package in packages))
        self.assertTrue(any("checksums" in package for package in packages))
        self.assertEqual(
            len({package["SPDXID"] for package in packages}),
            len(packages),
        )
        with tempfile.TemporaryDirectory(dir=ROOT / "backend" / "tests") as temp_dir:
            output = Path(temp_dir) / "frontend.spdx.json"
            write_sbom("frontend", packages, output)
            document = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(document["packages"]), len(packages))
            self.assertTrue(document["relationships"])

    def test_unparseable_license_metadata_is_not_promoted_to_spdx_expression(self):
        self.assertEqual(_npm_spdx_license("(MIT OR Apache-2.0)")[0], "(MIT OR Apache-2.0)")
        expression, comment = _npm_spdx_license("SEE LICENSE IN LICENSE")
        self.assertEqual(expression, "NOASSERTION")
        self.assertIn("SEE LICENSE", comment)

    def test_sbom_and_checksum_outputs_are_valid_and_stable(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "backend" / "tests") as temp_dir:
            folder = Path(temp_dir)
            sbom_path = folder / "sbom.spdx.json"
            checksum_path = folder / "SHA256SUMS"
            write_sbom(
                "test",
                [
                    {
                        "name": "example",
                        "SPDXID": "SPDXRef-example-1",
                        "versionInfo": "1.0",
                        "downloadLocation": "NOASSERTION",
                        "filesAnalyzed": False,
                        "licenseConcluded": "NOASSERTION",
                        "licenseDeclared": "MIT",
                        "copyrightText": "NOASSERTION",
                        "externalRefs": [
                            {
                                "referenceType": "purl",
                                "referenceLocator": "pkg:npm/example@1.0",
                            }
                        ],
                    }
                ],
                sbom_path,
            )
            write_checksums([sbom_path], checksum_path)
            document = json.loads(sbom_path.read_text(encoding="utf-8"))
            expected_digest = hashlib.sha256(sbom_path.read_bytes()).hexdigest()
            self.assertEqual(document["spdxVersion"], "SPDX-2.3")
            self.assertIn(expected_digest, checksum_path.read_text(encoding="utf-8"))
            license_path = folder / "licenses.json"
            write_license_inventory([sbom_path], license_path)
            licenses = json.loads(license_path.read_text(encoding="utf-8"))
            self.assertEqual(licenses["packages"][0]["license_declared"], "MIT")
            self.assertEqual(licenses["packages"][0]["ecosystem"], "npm")


if __name__ == "__main__":
    unittest.main()
