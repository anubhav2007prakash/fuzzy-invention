"""Tests for application configuration validation at startup."""
import os
import unittest
from unittest.mock import patch


class TestSettingsValidation(unittest.TestCase):
    """Test that Settings validates correctly at startup."""

    def test_default_settings_valid(self):
        """Default settings should be valid for development."""
        from backend.app.core.config import Settings
        s = Settings()
        self.assertEqual(s.ENVIRONMENT, "development")
        self.assertEqual(s.RANDOM_SEED, 42)
        self.assertEqual(s.TRAIN_RATIO, 0.8)

    def test_train_ratio_bounds(self):
        """TRAIN_RATIO must be between 0.1 and 0.95."""
        from backend.app.core.config import Settings
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            Settings(TRAIN_RATIO=0.01)

        with self.assertRaises(ValidationError):
            Settings(TRAIN_RATIO=0.99)

    def test_upload_size_minimum(self):
        """MAX_UPLOAD_SIZE_BYTES must be at least 1024."""
        from backend.app.core.config import Settings
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            Settings(MAX_UPLOAD_SIZE_BYTES=100)

    def test_log_level_validation(self):
        """LOG_LEVEL must be a valid Python logging level."""
        from backend.app.core.config import Settings
        from pydantic import ValidationError

        # Valid levels should work
        s = Settings(LOG_LEVEL="DEBUG")
        self.assertEqual(s.LOG_LEVEL, "DEBUG")

        s = Settings(LOG_LEVEL="WARNING")
        self.assertEqual(s.LOG_LEVEL, "WARNING")

        # Invalid level should fail
        with self.assertRaises(ValidationError):
            Settings(LOG_LEVEL="INVALID_LEVEL")

    def test_production_rejects_default_secret(self):
        """Production environment must not accept default SECRET_KEY."""
        from backend.app.core.config import Settings
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="default-secret-key-change-in-production",
            )

    def test_production_accepts_custom_secret(self):
        """Production with a custom SECRET_KEY should be valid."""
        from backend.app.core.config import Settings

        s = Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a-secure-random-key-for-production",
        )
        self.assertEqual(s.SECRET_KEY, "a-secure-random-key-for-production")

    def test_staging_rejects_default_secret(self):
        """Staging environment must not accept default SECRET_KEY."""
        from backend.app.core.config import Settings
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            Settings(
                ENVIRONMENT="staging",
                SECRET_KEY="default-secret-key-change-in-production",
            )

    def test_directories_created(self):
        """Data directories should be created if they don't exist."""
        from backend.app.core.config import Settings
        s = Settings()
        self.assertTrue(s.DATA_RAW_DIR.exists())
        self.assertTrue(s.DATA_PROCESSED_DIR.exists())
        self.assertTrue(s.MODELS_TRAINED_DIR.exists())
        self.assertTrue(s.MODELS_ARTIFACTS_DIR.exists())
        self.assertTrue(s.RESULTS_DIR.exists())


if __name__ == "__main__":
    unittest.main()
