"""Tests for API validation — UUID format checking and consistent error responses."""
import unittest

from backend.app.core.exceptions import validate_uuid_format


class TestUUIDValidation(unittest.TestCase):
    """Test validate_uuid_format utility."""

    def test_valid_uuid_passes(self):
        valid_id = "550e8400-e29b-41d4-a716-446655440000"
        result = validate_uuid_format(valid_id, "test")
        self.assertEqual(result, valid_id)

    def test_valid_uuid_lowercase(self):
        valid_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        result = validate_uuid_format(valid_id, "test")
        self.assertEqual(result, valid_id)

    def test_valid_uuid_uppercase(self):
        valid_id = "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"
        result = validate_uuid_format(valid_id, "test")
        self.assertEqual(result, valid_id)

    def test_empty_string_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            validate_uuid_format("", "test")
        self.assertIn("empty", str(ctx.exception).lower())

    def test_none_rejected(self):
        with self.assertRaises(ValueError):
            validate_uuid_format(None, "test")

    def test_non_uuid_string_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            validate_uuid_format("not-a-uuid", "test")
        self.assertIn("Invalid", str(ctx.exception))

    def test_sql_injection_rejected(self):
        with self.assertRaises(ValueError):
            validate_uuid_format("'; DROP TABLE users; --", "test")

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            validate_uuid_format("../../../etc/passwd", "test")

    def test_too_short_rejected(self):
        with self.assertRaises(ValueError):
            validate_uuid_format("550e8400-e29b-41d4", "test")

    def test_integer_rejected(self):
        with self.assertRaises(ValueError):
            validate_uuid_format(12345, "test")

    def test_resource_type_in_error(self):
        with self.assertRaises(ValueError) as ctx:
            validate_uuid_format("bad-id", "model")
        self.assertIn("model", str(ctx.exception).lower())


class TestExceptionToDict(unittest.TestCase):
    """Test SentinelCryptException.to_dict() for consistent error format."""

    def test_to_dict_structure(self):
        from backend.app.core.exceptions import (
            ModelNotFoundError,
            InvalidDatasetError,
        )
        exc = ModelNotFoundError("abc-123")
        d = exc.to_dict()
        self.assertIn("error", d)
        self.assertIn("code", d["error"])
        self.assertIn("message", d["error"])
        self.assertIn("details", d["error"])
        self.assertEqual(d["error"]["code"], "MODEL_NOT_FOUND")
        self.assertIn("abc-123", d["error"]["message"])

    def test_invalid_dataset_to_dict(self):
        from backend.app.core.exceptions import InvalidDatasetError
        exc = InvalidDatasetError("File is corrupted")
        d = exc.to_dict()
        self.assertEqual(d["error"]["code"], "INVALID_DATASET")


if __name__ == "__main__":
    unittest.main()
