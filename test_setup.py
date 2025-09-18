#!/usr/bin/env python3
"""
Test script to verify that the basic setup is working correctly.
This script tests configuration loading, database connection, and basic functionality.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from src.core.config import settings, validate_configuration, print_configuration_status
    from src.core.logger import get_logger, setup_logging
    from src.core.database import create_tables, health_check, check_database_connection
    from src.core.exceptions import TelegramAssistantException

    # Setup logging for testing
    setup_logging()
    logger = get_logger(__name__)

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure all dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)


async def test_configuration():
    """Test configuration loading and validation."""
    print("\n🔧 Testing Configuration...")

    try:
        # Test settings access
        print(f"   App Name: {settings.app_name}")
        print(f"   Environment: {settings.environment}")
        print(f"   Debug Mode: {settings.debug}")

        # Validate configuration
        config_status = validate_configuration()

        if config_status["valid"]:
            print("   ✅ Configuration validation passed")

            # Show service status
            services = config_status["services"]
            print(f"   📋 Services configured:")
            for service, configured in services.items():
                icon = "✅" if configured else "❌"
                print(f"      {icon} {service.replace('_', ' ').title()}")

        else:
            print("   ❌ Configuration validation failed:")
            for error in config_status["errors"]:
                print(f"      - {error}")

        return config_status["valid"]

    except Exception as e:
        print(f"   ❌ Configuration test failed: {e}")
        return False


async def test_database():
    """Test database connection and setup."""
    print("\n🗄️  Testing Database...")

    try:
        # Test database connection
        connected = await check_database_connection()
        if connected:
            print("   ✅ Database connection successful")
        else:
            print("   ❌ Database connection failed")
            return False

        # Test table creation
        await create_tables()
        print("   ✅ Database tables created/verified")

        # Test health check
        health = await health_check()
        if health["status"] == "healthy":
            print("   ✅ Database health check passed")
        else:
            print(f"   ⚠️  Database health check issues: {health}")

        return True

    except Exception as e:
        print(f"   ❌ Database test failed: {e}")
        return False


def test_utilities():
    """Test utility functions."""
    print("\n🛠️  Testing Utilities...")

    try:
        # Test file utilities
        from src.utils.file_utils import is_supported_file_type, format_file_size

        # Test file type validation
        pdf_supported = is_supported_file_type("test.pdf")
        exe_supported = is_supported_file_type("test.exe")
        print(f"   📄 PDF supported: {'✅' if pdf_supported else '❌'}")
        print(f"   📄 EXE supported: {'✅' if not exe_supported else '❌'} (should be false)")

        # Test size formatting
        formatted_size = format_file_size(1048576)  # 1MB
        print(f"   📊 Size formatting: {formatted_size}")

        # Test text utilities
        from src.utils.text_utils import clean_text, count_words

        sample_text = "  This is   a test   text.  "
        cleaned = clean_text(sample_text)
        word_count = count_words(cleaned)
        print(f"   📝 Text cleaning: '{cleaned}' ({word_count} words)")

        # Test validation utilities
        from src.utils.validation_utils import validate_email, ValidationError

        try:
            validate_email("test@example.com")
            print("   ✅ Email validation working")
        except ValidationError:
            print("   ❌ Email validation failed")

        print("   ✅ Utility functions working")
        return True

    except Exception as e:
        print(f"   ❌ Utilities test failed: {e}")
        return False


def test_models():
    """Test data models."""
    print("\n📊 Testing Data Models...")

    try:
        from src.models import (
            DocumentCreate, ChatMessageCreate, FileMetadataCreate,
            UserProfileCreate, ProcessingJobCreate
        )

        # Test document model
        doc = DocumentCreate(
            file_id="test_file_123",
            original_filename="test.pdf",
            file_type="pdf",
            file_size_bytes=1024,
            google_drive_id="test_drive_id"
        )
        print(f"   📄 Document model: {doc.file_id}")

        # Test chat message model
        msg = ChatMessageCreate(
            chat_id="123456",
            message_type="user",
            content="Hello, world!",
            user_id="user123"
        )
        print(f"   💬 Chat message model: {msg.content}")

        # Test file metadata model
        file_meta = FileMetadataCreate(
            file_id="file_123",
            original_filename="test.pdf",
            file_extension="pdf",
            file_size_bytes=1024,
            source="google_drive"
        )
        print(f"   📁 File metadata model: {file_meta.file_id}")

        print("   ✅ Data models working")
        return True

    except Exception as e:
        print(f"   ❌ Models test failed: {e}")
        return False


async def test_fastapi_app():
    """Test FastAPI application."""
    print("\n🚀 Testing FastAPI Application...")

    try:
        from main import app
        from fastapi.testclient import TestClient

        # This would normally require TestClient, but we'll just test import
        print("   ✅ FastAPI app imports successfully")
        print(f"   📝 App title: {app.title}")
        print(f"   📝 App version: {app.version}")

        return True

    except Exception as e:
        print(f"   ❌ FastAPI test failed: {e}")
        return False


def test_environment_file():
    """Test if .env file exists and has required variables."""
    print("\n🌍 Testing Environment File...")

    env_file = Path(".env")

    if not env_file.exists():
        print("   ❌ .env file not found")
        print("      Create .env file by copying .env.example and filling in your values")
        return False

    print("   ✅ .env file exists")

    # Check for key variables
    required_vars = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "GOOGLE_GEMINI_API_KEY"
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"   ⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("      Fill in these values in your .env file")
    else:
        print("   ✅ Key environment variables are set")

    return len(missing_vars) == 0


async def run_all_tests():
    """Run all tests and provide summary."""
    print("🧪 TELEGRAM ASSISTANT - SETUP VALIDATION")
    print("=" * 50)

    results = []

    # Test environment file first
    results.append(("Environment File", test_environment_file()))

    # Test configuration
    results.append(("Configuration", await test_configuration()))

    # Test database
    results.append(("Database", await test_database()))

    # Test utilities
    results.append(("Utilities", test_utilities()))

    # Test models
    results.append(("Data Models", test_models()))

    # Test FastAPI app
    results.append(("FastAPI App", await test_fastapi_app()))

    # Print summary
    print("\n" + "=" * 50)
    print("📋 TEST SUMMARY")
    print("=" * 50)

    passed = 0
    total = len(results)

    for test_name, result in results:
        icon = "✅" if result else "❌"
        print(f"{icon} {test_name}")
        if result:
            passed += 1

    print(f"\n🎯 Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Your setup is ready.")
        print("\n🚀 Next steps:")
        print("   1. Run 'python main.py' to start the development server")
        print("   2. Visit http://localhost:8000 to see your application")
        print("   3. Check http://localhost:8000/docs for API documentation")
    else:
        print(f"❌ {total - passed} tests failed. Please fix the issues above.")
        print("\n📖 Check the setup documentation for help:")
        print("   - SETUP_INSTRUCTIONS.md")
        print("   - PRE_DEVELOPMENT_CHECKLIST.md")

    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test runner failed: {e}")
        sys.exit(1)