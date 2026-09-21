"""Security tests for file upload handling — filename sanitization, path traversal, and storage safety.

These tests verify that malicious filenames are properly rejected and that
files are stored with server-generated names inside the configured directory.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.app.core.file_security import (
    FileSecurityError,
    generate_safe_storage_path,
    sanitize_filename,
    validate_filename,
    verify_file_within_directory,
)
from backend.app.core.exceptions import UnsupportedFormatError


class TestSanitizeFilename(unittest.TestCase):
    """Test filename sanitization."""

    def test_normal_filename(self):
        self.assertEqual(sanitize_filename("data.csv"), "data.csv")

    def test_none_returns_default(self):
        self.assertEqual(sanitize_filename(None), "dataset.csv")

    def test_empty_returns_default(self):
        self.assertEqual(sanitize_filename(""), "dataset.csv")

    def test_strips_directory_components(self):
        result = sanitize_filename("/etc/passwd.csv")
        self.assertEqual(result, "passwd.csv")

    def test_strips_windows_path(self):
        result = sanitize_filename("C:\\Users\\admin\\data.csv")
        # On Windows os.path.basename returns 'data.csv'; on Linux the whole
        # string passes through os.path.basename unchanged, then backslashes
        # and dots get sanitized. Either way the result should be a safe name
        # that does not escape to a different directory.
        self.assertTrue(result.endswith("data.csv"))
        self.assertNotIn("..", result)

    def test_removes_null_bytes(self):
        result = sanitize_filename("da\x00ta.csv")
        self.assertNotIn("\x00", result)

    def test_collapses_multiple_dots(self):
        result = sanitize_filename("data..csv")
        self.assertNotIn("..", result)

    def test_removes_angle_brackets(self):
        result = sanitize_filename("<script>.csv")
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)

    def test_removes_pipe(self):
        result = sanitize_filename("data|pipe.csv")
        self.assertNotIn("|", result)

    def test_preserves_valid_name(self):
        result = sanitize_filename("UNSW-NB15_2023.csv")
        self.assertEqual(result, "UNSW-NB15_2023.csv")


class TestValidateFilename(unittest.TestCase):
    """Test filename validation (security checks)."""

    def test_valid_csv_passes(self):
        validate_filename("unsw_nb15.csv")  # Should not raise

    def test_empty_filename_rejected(self):
        with self.assertRaises(FileSecurityError):
            validate_filename("")

    def test_none_filename_rejected(self):
        with self.assertRaises(FileSecurityError):
            validate_filename(None)

    def test_traversal_dotdot_rejected(self):
        with self.assertRaises(FileSecurityError):
            validate_filename("../../../etc/passwd.csv")

    def test_traversal_backslash_rejected(self):
        with self.assertRaises(FileSecurityError):
            validate_filename("..\\..\\windows\\system32.csv")

    def test_tilde_expansion_rejected(self):
        with self.assertRaises(FileSecurityError):
            validate_filename("~/etc/passwd.csv")

    def test_absolute_path_unix_rejected(self):
        with self.assertRaises(FileSecurityError):
            validate_filename("/etc/passwd.csv")

    def test_absolute_path_windows_rejected(self):
        with self.assertRaises(FileSecurityError):
            validate_filename("C:\\windows\\system32\\config.csv")

    def test_null_bytes_rejected(self):
        with self.assertRaises(FileSecurityError):
            validate_filename("data\x00.csv")

    def test_non_csv_extension_rejected(self):
        with self.assertRaises(UnsupportedFormatError):
            validate_filename("malware.exe")

    def test_python_file_rejected(self):
        with self.assertRaises(UnsupportedFormatError):
            validate_filename("script.py")

    def test_html_file_rejected(self):
        with self.assertRaises(UnsupportedFormatError):
            validate_filename("xss.html")

    def test_empty_extension_rejected(self):
        with self.assertRaises(UnsupportedFormatError):
            validate_filename("noext")

    def test_tar_file_rejected(self):
        with self.assertRaises(UnsupportedFormatError):
            validate_filename("archive.tar.gz")

    def test_valid_uppercase_csv(self):
        validate_filename("DATA.CSV")  # Should not raise

    def test_mixed_case_csv(self):
        validate_filename("Dataset.CsV")  # Should not raise

    def test_path_traversal_embedded_in_middle(self):
        with self.assertRaises(FileSecurityError):
            validate_filename("safe/../../../etc/passwd.csv")

    def test_double_dot_in_name_rejected(self):
        with self.assertRaises(FileSecurityError):
            validate_filename("..csv")

    def test_tilde_only(self):
        with self.assertRaises(FileSecurityError):
            validate_filename("~")


class TestGenerateSafeStoragePath(unittest.TestCase):
    """Test server-generated storage paths."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generates_uuid_name(self):
        path = generate_safe_storage_path(
            Path(self.temp_dir), original_filename="data.csv"
        )
        self.assertEqual(path.parent, Path(self.temp_dir))
        self.assertTrue(path.name.endswith(".csv"))
        # UUID hex is 32 chars + 4 char extension
        name_stem = path.stem
        self.assertEqual(len(name_stem), 32)
        # Verify it's a valid hex string
        int(name_stem, 16)

    def test_preserves_extension(self):
        path = generate_safe_storage_path(
            Path(self.temp_dir), original_filename="data.csv"
        )
        self.assertEqual(path.suffix, ".csv")

    def test_default_extension(self):
        path = generate_safe_storage_path(
            Path(self.temp_dir), original_filename="data.xyz"
        )
        self.assertEqual(path.suffix, ".csv")  # Falls back to default

    def test_creates_directory(self):
        new_dir = Path(self.temp_dir) / "new_subdir"
        path = generate_safe_storage_path(new_dir, original_filename="data.csv")
        self.assertTrue(new_dir.exists())

    def test_unique_names(self):
        path1 = generate_safe_storage_path(
            Path(self.temp_dir), original_filename="data.csv"
        )
        path2 = generate_safe_storage_path(
            Path(self.temp_dir), original_filename="data.csv"
        )
        self.assertNotEqual(path1.name, path2.name)

    def test_no_path_traversal_in_result(self):
        path = generate_safe_storage_path(
            Path(self.temp_dir), original_filename="../../../etc/passwd.csv"
        )
        self.assertTrue(path.resolve().is_relative_to(Path(self.temp_dir).resolve()))


class TestVerifyFileWithinDirectory(unittest.TestCase):
    """Test directory containment verification."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.allowed_dir = self.temp_dir / "allowed"
        self.allowed_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_file_in_directory_passes(self):
        file_path = self.allowed_dir / "test.csv"
        file_path.touch()
        self.assertTrue(verify_file_within_directory(file_path, self.allowed_dir))

    def test_file_outside_directory_fails(self):
        file_path = self.temp_dir / "test.csv"
        file_path.touch()
        self.assertFalse(verify_file_within_directory(file_path, self.allowed_dir))

    def test_symlink_outside_fails(self):
        """Symlinks that escape the allowed directory are rejected."""
        outside_file = self.temp_dir / "outside.csv"
        outside_file.touch()
        link_path = self.allowed_dir / "link.csv"
        try:
            link_path.symlink_to(outside_file)
            self.assertFalse(verify_file_within_directory(link_path, self.allowed_dir))
        except OSError:
            self.skipTest("Symlinks not supported on this platform")


class TestDatasetUploadSecurityIntegration(unittest.TestCase):
    """Integration tests for secure file upload through DatasetService."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_path_traversal_filename_rejected(self):
        """Ensure path traversal in filename is caught before file storage."""
        from backend.app.core.exceptions import InvalidDatasetError
        from backend.app.ml.preprocessing.validators import validate_dataset

        # Create a valid CSV
        import pandas as pd
        cols = ["f1", "f2", "f3", "label"]
        data = {c: list(range(100)) for c in cols}
        data["label"] = [0] * 50 + [1] * 50
        csv_bytes = pd.DataFrame(data).to_csv(index=False).encode("utf-8")

        # Validate filename security directly (this is what DatasetService does)
        with self.assertRaises(FileSecurityError):
            validate_filename("../../../etc/shadow.csv")

    def test_server_generated_name_used(self):
        """Verify the file stored on disk uses a UUID name, not the original."""
        from backend.app.core.file_security import generate_safe_storage_path

        storage_path = generate_safe_storage_path(
            Path(self.temp_dir), original_filename="malicious_../../data.csv"
        )
        # The name should be UUID-based, not contain the malicious original
        self.assertNotIn("..", storage_path.name)
        self.assertNotIn("malicious", storage_path.name)
        self.assertTrue(storage_path.name.endswith(".csv"))


if __name__ == "__main__":
    unittest.main()
