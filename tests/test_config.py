"""
Tests for configuration management and validation.
"""

import pytest
import os
from unittest.mock import patch
from pydantic import ValidationError

from src.core.config import Settings, validate_configuration, print_configuration_status


class TestSettings:
    """Test Settings model and validation."""

    def test_settings_with_valid_env(self, test_settings):
        """Test that settings load correctly with valid environment variables."""
        settings = test_settings

        assert settings.app_name == "Telegram Assistant"
        assert settings.environment == "testing"
        assert settings.debug is True
        assert settings.telegram_bot_token.startswith("123456789:")
        assert settings.google_gemini_api_key.startswith("AIza")
        assert settings.database_url == "sqlite+aiosqlite:///:memory:"

    def test_settings_with_missing_env(self, mock_env_missing):
        """Test that settings raise validation error with missing environment variables."""
        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        error_fields = [error["loc"][0] for error in errors]

        # Check that required fields are missing
        assert "telegram_bot_token" in error_fields
        assert "google_gemini_api_key" in error_fields

    def test_settings_with_invalid_env(self, mock_env_invalid):
        """Test that settings raise validation error with invalid values."""
        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()

        # Should have validation errors for invalid formats
        assert len(errors) > 0

    def test_telegram_token_validation(self):
        """Test Telegram token format validation."""
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': 'invalid-token',
            'GOOGLE_GEMINI_API_KEY': 'AIzaSyTest123456789012345678901234567890',
        }):
            with pytest.raises(ValidationError) as exc_info:
                Settings()

            errors = exc_info.value.errors()
            token_errors = [e for e in errors if e["loc"][0] == "telegram_bot_token"]
            assert len(token_errors) > 0

    def test_gemini_api_key_validation(self):
        """Test Google Gemini API key format validation."""
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': '123456789:ABCdefGhIjKlMnOpQrStUvWxYz123456789',
            'GOOGLE_GEMINI_API_KEY': 'invalid-key',
        }):
            with pytest.raises(ValidationError) as exc_info:
                Settings()

            errors = exc_info.value.errors()
            key_errors = [e for e in errors if e["loc"][0] == "google_gemini_api_key"]
            assert len(key_errors) > 0

    def test_database_url_defaults(self, test_settings):
        """Test database URL defaults to SQLite in memory for testing."""
        settings = test_settings
        assert "sqlite+aiosqlite" in settings.database_url

    def test_optional_services(self, test_settings):
        """Test that optional services can be None."""
        settings = test_settings

        # These should be set in test environment
        assert settings.pinecone_api_key is not None
        assert settings.google_drive_folder_id is not None

        # Test with missing optional services
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': '123456789:ABCdefGhIjKlMnOpQrStUvWxYz123456789',
            'GOOGLE_GEMINI_API_KEY': 'AIzaSyTest123456789012345678901234567890',
        }):
            settings_minimal = Settings()
            assert settings_minimal.pinecone_api_key is None
            assert settings_minimal.supabase_url is None


class TestConfigurationValidation:
    """Test configuration validation functions."""

    def test_validate_configuration_success(self, test_settings):
        """Test successful configuration validation."""
        result = validate_configuration()

        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert "services" in result

        services = result["services"]
        assert services["telegram"] is True
        assert services["google_gemini"] is True
        assert services["google_drive"] is True
        assert services["pinecone"] is True

    def test_validate_configuration_missing_required(self, mock_env_missing):
        """Test configuration validation with missing required variables."""
        result = validate_configuration()

        assert result["valid"] is False
        assert len(result["errors"]) > 0

        # Check that errors mention missing environment variables
        error_text = " ".join(result["errors"])
        assert "TELEGRAM_BOT_TOKEN" in error_text or "telegram" in error_text.lower()

    def test_validate_configuration_invalid_values(self, mock_env_invalid):
        """Test configuration validation with invalid values."""
        result = validate_configuration()

        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_print_configuration_status(self, test_settings, capsys):
        """Test configuration status printing."""
        print_configuration_status()

        captured = capsys.readouterr()
        assert "Configuration Status" in captured.out
        assert "Telegram Assistant" in captured.out

    def test_service_configuration_detection(self, test_settings):
        """Test that service configuration is properly detected."""
        result = validate_configuration()
        services = result["services"]

        # Test individual service detection
        assert isinstance(services["telegram"], bool)
        assert isinstance(services["google_gemini"], bool)
        assert isinstance(services["google_drive"], bool)
        assert isinstance(services["pinecone"], bool)
        assert isinstance(services["supabase"], bool)

    def test_environment_specific_settings(self):
        """Test environment-specific configuration."""
        # Test development environment
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': '123456789:ABCdefGhIjKlMnOpQrStUvWxYz123456789',
            'GOOGLE_GEMINI_API_KEY': 'AIzaSyTest123456789012345678901234567890',
            'ENVIRONMENT': 'development',
            'DEBUG': 'true'
        }):
            settings = Settings()
            assert settings.environment == "development"
            assert settings.debug is True

        # Test production environment
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': '123456789:ABCdefGhIjKlMnOpQrStUvWxYz123456789',
            'GOOGLE_GEMINI_API_KEY': 'AIzaSyTest123456789012345678901234567890',
            'ENVIRONMENT': 'production',
            'DEBUG': 'false'
        }):
            settings = Settings()
            assert settings.environment == "production"
            assert settings.debug is False


class TestConfigurationIntegration:
    """Test configuration integration with other components."""

    def test_configuration_with_database(self, test_settings):
        """Test that configuration works with database setup."""
        settings = test_settings

        # Database URL should be properly formatted
        assert settings.database_url.startswith("sqlite+aiosqlite://")

        # Should work with async database operations
        from src.core.database import get_database_url
        db_url = get_database_url()
        assert db_url == settings.database_url

    def test_configuration_logging_integration(self, test_settings):
        """Test that configuration integrates with logging."""
        settings = test_settings

        assert settings.log_level == "DEBUG"

        # Test that logger respects configuration
        from src.core.logger import get_logger
        logger = get_logger("test")
        assert logger is not None

    @pytest.mark.slow
    def test_configuration_service_validation(self, test_settings):
        """Test that configuration validates external service connectivity."""
        # This would test actual API connectivity in a real scenario
        # For now, just test that the configuration is properly set up
        settings = test_settings

        # All required services should be configured
        assert settings.telegram_bot_token is not None
        assert settings.google_gemini_api_key is not None

        # Validate format requirements
        assert len(settings.telegram_bot_token.split(':')) == 2
        assert settings.google_gemini_api_key.startswith('AIza')