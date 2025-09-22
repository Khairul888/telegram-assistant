"""
Configuration management for Telegram Assistant.
Loads environment variables and provides centralized config access.
"""

import os
from typing import Optional, List
from pathlib import Path
try:
    from pydantic_settings import BaseSettings
    from pydantic import field_validator, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    # Fallback for basic configuration
    class BaseSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
    def field_validator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def Field(*args, **kwargs):
        return kwargs.get('default')


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # =============================================================================
    # APPLICATION SETTINGS
    # =============================================================================
    app_name: str = "Telegram Assistant"
    version: str = "1.0.0"
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=True, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # =============================================================================
    # TELEGRAM CONFIGURATION
    # =============================================================================
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(..., env="TELEGRAM_CHAT_ID")

    @field_validator("telegram_bot_token")
    @classmethod
    def validate_telegram_token(cls, v):
        if not v or not v.strip():
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if not (":" in v and len(v.split(":")[0]) >= 8):
            raise ValueError("TELEGRAM_BOT_TOKEN format appears invalid")
        return v.strip()

    @field_validator("telegram_chat_id")
    @classmethod
    def validate_chat_id(cls, v):
        if not v or not v.strip():
            raise ValueError("TELEGRAM_CHAT_ID is required")
        try:
            int(v.strip())
        except ValueError:
            raise ValueError("TELEGRAM_CHAT_ID must be a valid number")
        return v.strip()

    # =============================================================================
    # GOOGLE SERVICES CONFIGURATION
    # =============================================================================
    google_gemini_api_key: str = Field(..., env="GOOGLE_GEMINI_API_KEY")
    google_service_account_json_path: Optional[str] = Field(None, env="GOOGLE_SERVICE_ACCOUNT_JSON_PATH")
    google_service_account_json: Optional[str] = Field(None, env="GOOGLE_SERVICE_ACCOUNT_JSON")
    google_drive_folder_id: str = Field(..., env="GOOGLE_DRIVE_FOLDER_ID")
    google_docs_history_id: Optional[str] = Field(None, env="GOOGLE_DOCS_HISTORY_ID")

    @field_validator("google_gemini_api_key")
    @classmethod
    def validate_gemini_key(cls, v):
        if not v or not v.strip():
            raise ValueError("GOOGLE_GEMINI_API_KEY is required")
        return v.strip()

    @field_validator("google_service_account_json_path")
    @classmethod
    def validate_service_account_path(cls, v):
        # Skip validation if no path provided or if it's a placeholder
        if not v or "your" in v.lower() or "telegram-assistant" in v:
            return None
        if not Path(v).exists():
            raise ValueError(f"Service account JSON file not found: {v}")
        return v

    # =============================================================================
    # VECTOR DATABASE CONFIGURATION (Choose one)
    # =============================================================================
    # Pinecone (Option A - matches n8n workflow)
    pinecone_api_key: Optional[str] = Field(None, env="PINECONE_API_KEY")
    pinecone_environment: Optional[str] = Field(None, env="PINECONE_ENVIRONMENT")
    pinecone_index_name: str = Field(default="wheeey", env="PINECONE_INDEX_NAME")

    # Supabase (Option B - all-in-one alternative)
    supabase_url: Optional[str] = Field(None, env="SUPABASE_URL")
    supabase_key: Optional[str] = Field(None, env="SUPABASE_KEY")

    # Remove the complex validator for now - we'll add it back later
    # @field_validator("pinecone_api_key")
    # @classmethod
    # def validate_vector_db_config(cls, v):
    #     return v

    # =============================================================================
    # DATABASE CONFIGURATION
    # =============================================================================
    database_url: str = Field(default="sqlite:///./telegram_assistant.db", env="DATABASE_URL")

    # =============================================================================
    # AI PROCESSING SETTINGS
    # =============================================================================
    chunk_size: int = Field(default=3000, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, env="CHUNK_OVERLAP")
    max_tokens_per_request: int = Field(default=8192, env="MAX_TOKENS_PER_REQUEST")
    ai_temperature: float = Field(default=0.4, env="AI_TEMPERATURE")

    # Memory settings
    memory_window_size: int = Field(default=40, env="MEMORY_WINDOW_SIZE")
    memory_cleanup_days: int = Field(default=30, env="MEMORY_CLEANUP_DAYS")

    # =============================================================================
    # FILE PROCESSING SETTINGS
    # =============================================================================
    max_file_size_mb: int = Field(default=50, env="MAX_FILE_SIZE_MB")
    supported_file_types: List[str] = Field(
        default=["pdf", "docx", "txt", "jpg", "jpeg", "png", "xlsx", "csv"],
        env="SUPPORTED_FILE_TYPES"
    )

    @field_validator("supported_file_types", mode="before")
    @classmethod
    def parse_file_types(cls, v):
        if isinstance(v, str):
            return [ext.strip().lower() for ext in v.split(",")]
        return v

    # =============================================================================
    # WEBHOOK CONFIGURATION
    # =============================================================================
    app_base_url: Optional[str] = Field(None, env="APP_BASE_URL")
    telegram_webhook_url: Optional[str] = Field(None, env="TELEGRAM_WEBHOOK_URL")
    google_drive_webhook_url: Optional[str] = Field(None, env="GOOGLE_DRIVE_WEBHOOK_URL")

    # =============================================================================
    # OPTIONAL SERVICES
    # =============================================================================
    # Cloudinary
    cloudinary_cloud_name: Optional[str] = Field(None, env="CLOUDINARY_CLOUD_NAME")
    cloudinary_api_key: Optional[str] = Field(None, env="CLOUDINARY_API_KEY")
    cloudinary_api_secret: Optional[str] = Field(None, env="CLOUDINARY_API_SECRET")

    # Sentry for error tracking
    sentry_dsn: Optional[str] = Field(None, env="SENTRY_DSN")

    # Development settings
    skip_webhook_verification: bool = Field(default=False, env="SKIP_WEBHOOK_VERIFICATION")
    use_mock_responses: bool = Field(default=False, env="USE_MOCK_RESPONSES")

    # =============================================================================
    # COMPUTED PROPERTIES
    # =============================================================================
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"

    @property
    def use_pinecone(self) -> bool:
        """Check if Pinecone is configured and should be used."""
        return bool(self.pinecone_api_key and self.pinecone_environment)

    @property
    def use_supabase(self) -> bool:
        """Check if Supabase is configured and should be used."""
        return bool(self.supabase_url and self.supabase_key)

    @property
    def max_file_size_bytes(self) -> int:
        """Convert max file size from MB to bytes."""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def webhook_urls(self) -> dict:
        """Get all webhook URLs."""
        base_url = self.app_base_url
        if not base_url:
            return {}

        return {
            "telegram": f"{base_url}/api/telegram-webhook",
            "google_drive": f"{base_url}/api/drive-webhook",
            "health": f"{base_url}/api/health",
            "chat": f"{base_url}/api/chat"
        }

    # =============================================================================
    # PYDANTIC SETTINGS CONFIG
    # =============================================================================
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        validate_assignment = True

        # Allow extra fields for flexibility
        extra = "allow"


# =============================================================================
# GLOBAL SETTINGS INSTANCE
# =============================================================================
def get_settings() -> Settings:
    """Get application settings (cached)."""
    if PYDANTIC_AVAILABLE:
        return Settings()
    else:
        # Fallback: basic environment variable loading
        return Settings(
            app_name="Telegram Assistant",
            version="1.0.0",
            environment=os.getenv("ENVIRONMENT", "development"),
            debug=os.getenv("DEBUG", "True").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            google_gemini_api_key=os.getenv("GOOGLE_GEMINI_API_KEY", ""),
            google_drive_folder_id=os.getenv("GOOGLE_DRIVE_FOLDER_ID", ""),
            max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "50")),
            supported_file_types=os.getenv("SUPPORTED_FILE_TYPES", "pdf,docx,txt,jpg,jpeg,png,xlsx,csv").split(",")
        )


# Global settings instance
settings = get_settings()


# =============================================================================
# CONFIGURATION UTILITIES
# =============================================================================
def validate_configuration() -> dict:
    """
    Validate all configuration settings and return status report.

    Returns:
        dict: Configuration validation report
    """
    try:
        # Try to instantiate settings (this runs all validators)
        config = get_settings()

        status = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "services": {
                "telegram": bool(config.telegram_bot_token and config.telegram_chat_id),
                "google_gemini": bool(config.google_gemini_api_key),
                "google_drive": bool(config.google_drive_folder_id),
                "vector_db": config.use_pinecone or config.use_supabase,
                "pinecone": config.use_pinecone,
                "supabase": config.use_supabase,
                "cloudinary": bool(config.cloudinary_cloud_name),
                "sentry": bool(config.sentry_dsn)
            }
        }

        # Check for warnings
        if not config.google_service_account_json_path and not config.google_service_account_json:
            status["warnings"].append("Google Service Account credentials not configured")

        if not config.google_docs_history_id:
            status["warnings"].append("Google Docs history logging not configured")

        if config.is_production and config.debug:
            status["warnings"].append("DEBUG mode enabled in production")

        return status

    except Exception as e:
        return {
            "valid": False,
            "errors": [str(e)],
            "warnings": [],
            "services": {}
        }


def print_configuration_status():
    """Print a human-readable configuration status report."""
    status = validate_configuration()

    print(f"\n{'='*60}")
    print("TELEGRAM ASSISTANT - CONFIGURATION STATUS")
    print(f"{'='*60}")

    if status["valid"]:
        print("[OK] Configuration: VALID")
    else:
        print("[ERROR] Configuration: INVALID")
        for error in status["errors"]:
            print(f"   [ERROR] {error}")

    print(f"\nService Status:")
    services = status["services"]
    for service, enabled in services.items():
        icon = "[OK]" if enabled else "[X]"
        print(f"   {icon} {service.replace('_', ' ').title()}")

    if status["warnings"]:
        print(f"\n[WARNING] Warnings:")
        for warning in status["warnings"]:
            print(f"   [WARNING] {warning}")

    print(f"\nEnvironment: {settings.environment.upper()}")
    print(f"Debug Mode: {'ON' if settings.debug else 'OFF'}")
    print(f"Log Level: {settings.log_level}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    # Run configuration validation when script is executed directly
    print_configuration_status()