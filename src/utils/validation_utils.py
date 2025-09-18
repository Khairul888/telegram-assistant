"""
Data validation utilities for Telegram Assistant.
Provides validation functions for various data types and formats.
"""

import re
import hashlib
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime
from urllib.parse import urlparse

from ..core.logger import get_logger
from ..core.exceptions import ValidationError

logger = get_logger(__name__)


# =============================================================================
# BASIC DATA VALIDATION
# =============================================================================

def validate_required_field(value: Any, field_name: str) -> Any:
    """
    Validate that a required field has a value.

    Args:
        value: Value to check
        field_name: Name of the field for error messages

    Returns:
        The value if valid

    Raises:
        ValidationError: If field is empty or None
    """
    if value is None:
        raise ValidationError(
            f"{field_name} is required",
            error_code="REQUIRED_FIELD_MISSING",
            details={"field_name": field_name}
        )

    if isinstance(value, str) and not value.strip():
        raise ValidationError(
            f"{field_name} cannot be empty",
            error_code="REQUIRED_FIELD_EMPTY",
            details={"field_name": field_name}
        )

    return value


def validate_string_length(
    value: str,
    field_name: str,
    min_length: int = None,
    max_length: int = None
) -> str:
    """
    Validate string length.

    Args:
        value: String to validate
        field_name: Name of the field
        min_length: Minimum length (optional)
        max_length: Maximum length (optional)

    Returns:
        The string if valid

    Raises:
        ValidationError: If length is invalid
    """
    if not isinstance(value, str):
        raise ValidationError(
            f"{field_name} must be a string",
            error_code="INVALID_TYPE",
            details={"field_name": field_name, "expected_type": "string", "actual_type": type(value).__name__}
        )

    length = len(value)

    if min_length is not None and length < min_length:
        raise ValidationError(
            f"{field_name} must be at least {min_length} characters long",
            error_code="STRING_TOO_SHORT",
            details={"field_name": field_name, "min_length": min_length, "actual_length": length}
        )

    if max_length is not None and length > max_length:
        raise ValidationError(
            f"{field_name} must be at most {max_length} characters long",
            error_code="STRING_TOO_LONG",
            details={"field_name": field_name, "max_length": max_length, "actual_length": length}
        )

    return value


def validate_number_range(
    value: Union[int, float],
    field_name: str,
    min_value: Union[int, float] = None,
    max_value: Union[int, float] = None
) -> Union[int, float]:
    """
    Validate numeric range.

    Args:
        value: Number to validate
        field_name: Name of the field
        min_value: Minimum value (optional)
        max_value: Maximum value (optional)

    Returns:
        The number if valid

    Raises:
        ValidationError: If number is out of range
    """
    if not isinstance(value, (int, float)):
        raise ValidationError(
            f"{field_name} must be a number",
            error_code="INVALID_TYPE",
            details={"field_name": field_name, "expected_type": "number", "actual_type": type(value).__name__}
        )

    if min_value is not None and value < min_value:
        raise ValidationError(
            f"{field_name} must be at least {min_value}",
            error_code="NUMBER_TOO_SMALL",
            details={"field_name": field_name, "min_value": min_value, "actual_value": value}
        )

    if max_value is not None and value > max_value:
        raise ValidationError(
            f"{field_name} must be at most {max_value}",
            error_code="NUMBER_TOO_LARGE",
            details={"field_name": field_name, "max_value": max_value, "actual_value": value}
        )

    return value


def validate_list_length(
    value: List[Any],
    field_name: str,
    min_length: int = None,
    max_length: int = None
) -> List[Any]:
    """
    Validate list length.

    Args:
        value: List to validate
        field_name: Name of the field
        min_length: Minimum length (optional)
        max_length: Maximum length (optional)

    Returns:
        The list if valid

    Raises:
        ValidationError: If list length is invalid
    """
    if not isinstance(value, list):
        raise ValidationError(
            f"{field_name} must be a list",
            error_code="INVALID_TYPE",
            details={"field_name": field_name, "expected_type": "list", "actual_type": type(value).__name__}
        )

    length = len(value)

    if min_length is not None and length < min_length:
        raise ValidationError(
            f"{field_name} must contain at least {min_length} items",
            error_code="LIST_TOO_SHORT",
            details={"field_name": field_name, "min_length": min_length, "actual_length": length}
        )

    if max_length is not None and length > max_length:
        raise ValidationError(
            f"{field_name} must contain at most {max_length} items",
            error_code="LIST_TOO_LONG",
            details={"field_name": field_name, "max_length": max_length, "actual_length": length}
        )

    return value


# =============================================================================
# FORMAT VALIDATION
# =============================================================================

def validate_email(email: str) -> str:
    """
    Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        Cleaned email address

    Raises:
        ValidationError: If email format is invalid
    """
    if not isinstance(email, str):
        raise ValidationError(
            "Email must be a string",
            error_code="INVALID_EMAIL_TYPE"
        )

    email = email.strip().lower()

    if not email:
        raise ValidationError(
            "Email cannot be empty",
            error_code="EMPTY_EMAIL"
        )

    # Basic email regex pattern
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if not re.match(email_pattern, email):
        raise ValidationError(
            "Invalid email format",
            error_code="INVALID_EMAIL_FORMAT",
            details={"email": email}
        )

    # Additional checks
    if len(email) > 320:  # RFC 5321 limit
        raise ValidationError(
            "Email address too long",
            error_code="EMAIL_TOO_LONG",
            details={"email": email, "max_length": 320}
        )

    local_part, domain = email.split('@')

    if len(local_part) > 64:  # RFC 5321 limit
        raise ValidationError(
            "Email local part too long",
            error_code="EMAIL_LOCAL_PART_TOO_LONG",
            details={"email": email, "max_local_length": 64}
        )

    return email


def validate_url(url: str) -> str:
    """
    Validate URL format.

    Args:
        url: URL to validate

    Returns:
        Cleaned URL

    Raises:
        ValidationError: If URL format is invalid
    """
    if not isinstance(url, str):
        raise ValidationError(
            "URL must be a string",
            error_code="INVALID_URL_TYPE"
        )

    url = url.strip()

    if not url:
        raise ValidationError(
            "URL cannot be empty",
            error_code="EMPTY_URL"
        )

    try:
        parsed = urlparse(url)

        if not parsed.scheme:
            raise ValidationError(
                "URL must have a scheme (http/https)",
                error_code="MISSING_URL_SCHEME",
                details={"url": url}
            )

        if parsed.scheme not in ['http', 'https']:
            raise ValidationError(
                "URL scheme must be http or https",
                error_code="INVALID_URL_SCHEME",
                details={"url": url, "scheme": parsed.scheme}
            )

        if not parsed.netloc:
            raise ValidationError(
                "URL must have a domain",
                error_code="MISSING_URL_DOMAIN",
                details={"url": url}
            )

        return url

    except Exception as e:
        raise ValidationError(
            f"Invalid URL format: {str(e)}",
            error_code="INVALID_URL_FORMAT",
            details={"url": url}
        )


def validate_phone_number(phone: str) -> str:
    """
    Validate phone number format.

    Args:
        phone: Phone number to validate

    Returns:
        Cleaned phone number

    Raises:
        ValidationError: If phone format is invalid
    """
    if not isinstance(phone, str):
        raise ValidationError(
            "Phone number must be a string",
            error_code="INVALID_PHONE_TYPE"
        )

    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone.strip())

    if not cleaned:
        raise ValidationError(
            "Phone number cannot be empty",
            error_code="EMPTY_PHONE"
        )

    # Basic validation patterns
    patterns = [
        r'^\+?1?\d{10}$',  # US format
        r'^\+?\d{7,15}$',  # International format
    ]

    valid = any(re.match(pattern, cleaned) for pattern in patterns)

    if not valid:
        raise ValidationError(
            "Invalid phone number format",
            error_code="INVALID_PHONE_FORMAT",
            details={"phone": phone, "cleaned": cleaned}
        )

    return cleaned


# =============================================================================
# TELEGRAM-SPECIFIC VALIDATION
# =============================================================================

def validate_telegram_bot_token(token: str) -> str:
    """
    Validate Telegram bot token format.

    Args:
        token: Bot token to validate

    Returns:
        Token if valid

    Raises:
        ValidationError: If token format is invalid
    """
    if not isinstance(token, str):
        raise ValidationError(
            "Telegram bot token must be a string",
            error_code="INVALID_TOKEN_TYPE"
        )

    token = token.strip()

    if not token:
        raise ValidationError(
            "Telegram bot token cannot be empty",
            error_code="EMPTY_BOT_TOKEN"
        )

    # Telegram bot token format: {bot_id}:{bot_hash}
    if ':' not in token:
        raise ValidationError(
            "Invalid Telegram bot token format",
            error_code="INVALID_BOT_TOKEN_FORMAT",
            details={"expected_format": "bot_id:bot_hash"}
        )

    parts = token.split(':')
    if len(parts) != 2:
        raise ValidationError(
            "Invalid Telegram bot token format",
            error_code="INVALID_BOT_TOKEN_PARTS",
            details={"expected_parts": 2, "actual_parts": len(parts)}
        )

    bot_id, bot_hash = parts

    # Validate bot ID (should be numeric)
    if not bot_id.isdigit():
        raise ValidationError(
            "Bot ID must be numeric",
            error_code="INVALID_BOT_ID",
            details={"bot_id": bot_id}
        )

    # Validate bot hash (should be alphanumeric, typically 35 characters)
    if not re.match(r'^[A-Za-z0-9_-]+$', bot_hash):
        raise ValidationError(
            "Bot hash contains invalid characters",
            error_code="INVALID_BOT_HASH",
            details={"bot_hash": bot_hash}
        )

    if len(bot_hash) < 30:
        raise ValidationError(
            "Bot hash too short",
            error_code="BOT_HASH_TOO_SHORT",
            details={"bot_hash": bot_hash, "min_length": 30}
        )

    return token


def validate_telegram_chat_id(chat_id: str) -> str:
    """
    Validate Telegram chat ID.

    Args:
        chat_id: Chat ID to validate

    Returns:
        Chat ID if valid

    Raises:
        ValidationError: If chat ID is invalid
    """
    if not isinstance(chat_id, (str, int)):
        raise ValidationError(
            "Chat ID must be a string or number",
            error_code="INVALID_CHAT_ID_TYPE"
        )

    chat_id_str = str(chat_id).strip()

    if not chat_id_str:
        raise ValidationError(
            "Chat ID cannot be empty",
            error_code="EMPTY_CHAT_ID"
        )

    # Chat ID should be numeric (can be negative for groups)
    if not re.match(r'^-?\d+$', chat_id_str):
        raise ValidationError(
            "Chat ID must be numeric",
            error_code="INVALID_CHAT_ID_FORMAT",
            details={"chat_id": chat_id_str}
        )

    return chat_id_str


# =============================================================================
# FILE VALIDATION
# =============================================================================

def validate_file_extension(filename: str, allowed_extensions: List[str]) -> str:
    """
    Validate file extension.

    Args:
        filename: Name of the file
        allowed_extensions: List of allowed extensions

    Returns:
        Filename if valid

    Raises:
        ValidationError: If extension is not allowed
    """
    if not isinstance(filename, str):
        raise ValidationError(
            "Filename must be a string",
            error_code="INVALID_FILENAME_TYPE"
        )

    filename = filename.strip()

    if not filename:
        raise ValidationError(
            "Filename cannot be empty",
            error_code="EMPTY_FILENAME"
        )

    if '.' not in filename:
        raise ValidationError(
            "Filename must have an extension",
            error_code="MISSING_FILE_EXTENSION",
            details={"filename": filename}
        )

    extension = filename.split('.')[-1].lower()
    allowed_extensions = [ext.lower().strip('.') for ext in allowed_extensions]

    if extension not in allowed_extensions:
        raise ValidationError(
            f"File extension '{extension}' is not allowed",
            error_code="INVALID_FILE_EXTENSION",
            details={
                "filename": filename,
                "extension": extension,
                "allowed_extensions": allowed_extensions
            }
        )

    return filename


def validate_file_size(size_bytes: int, max_size_bytes: int) -> int:
    """
    Validate file size.

    Args:
        size_bytes: File size in bytes
        max_size_bytes: Maximum allowed size in bytes

    Returns:
        Size if valid

    Raises:
        ValidationError: If size is too large
    """
    if not isinstance(size_bytes, int):
        raise ValidationError(
            "File size must be an integer",
            error_code="INVALID_FILE_SIZE_TYPE"
        )

    if size_bytes < 0:
        raise ValidationError(
            "File size cannot be negative",
            error_code="NEGATIVE_FILE_SIZE",
            details={"size_bytes": size_bytes}
        )

    if size_bytes > max_size_bytes:
        raise ValidationError(
            f"File size {size_bytes} bytes exceeds maximum {max_size_bytes} bytes",
            error_code="FILE_TOO_LARGE",
            details={
                "size_bytes": size_bytes,
                "max_size_bytes": max_size_bytes,
                "size_mb": round(size_bytes / 1024 / 1024, 2),
                "max_size_mb": round(max_size_bytes / 1024 / 1024, 2)
            }
        )

    return size_bytes


# =============================================================================
# API KEY VALIDATION
# =============================================================================

def validate_api_key(api_key: str, key_name: str, min_length: int = 20) -> str:
    """
    Validate API key format.

    Args:
        api_key: API key to validate
        key_name: Name of the API key for error messages
        min_length: Minimum key length

    Returns:
        API key if valid

    Raises:
        ValidationError: If API key is invalid
    """
    if not isinstance(api_key, str):
        raise ValidationError(
            f"{key_name} must be a string",
            error_code="INVALID_API_KEY_TYPE",
            details={"key_name": key_name}
        )

    api_key = api_key.strip()

    if not api_key:
        raise ValidationError(
            f"{key_name} cannot be empty",
            error_code="EMPTY_API_KEY",
            details={"key_name": key_name}
        )

    if len(api_key) < min_length:
        raise ValidationError(
            f"{key_name} is too short (minimum {min_length} characters)",
            error_code="API_KEY_TOO_SHORT",
            details={
                "key_name": key_name,
                "min_length": min_length,
                "actual_length": len(api_key)
            }
        )

    return api_key


def validate_google_api_key(api_key: str) -> str:
    """
    Validate Google API key format.

    Args:
        api_key: Google API key

    Returns:
        API key if valid

    Raises:
        ValidationError: If API key format is invalid
    """
    api_key = validate_api_key(api_key, "Google API key", min_length=30)

    # Google API keys typically start with specific prefixes
    if not re.match(r'^[A-Za-z0-9_-]+$', api_key):
        raise ValidationError(
            "Google API key contains invalid characters",
            error_code="INVALID_GOOGLE_API_KEY_FORMAT",
            details={"api_key": api_key[:10] + "..."}  # Only show first 10 chars for security
        )

    return api_key


def validate_pinecone_api_key(api_key: str) -> str:
    """
    Validate Pinecone API key format.

    Args:
        api_key: Pinecone API key

    Returns:
        API key if valid

    Raises:
        ValidationError: If API key format is invalid
    """
    api_key = validate_api_key(api_key, "Pinecone API key", min_length=30)

    # Pinecone API keys are typically UUIDs with hyphens
    if not re.match(r'^[a-f0-9-]+$', api_key):
        raise ValidationError(
            "Pinecone API key format appears invalid",
            error_code="INVALID_PINECONE_API_KEY_FORMAT",
            details={"api_key": api_key[:10] + "..."}
        )

    return api_key


# =============================================================================
# DATA STRUCTURE VALIDATION
# =============================================================================

def validate_json_structure(data: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
    """
    Validate JSON data structure.

    Args:
        data: Dictionary to validate
        required_fields: List of required field names

    Returns:
        Data if valid

    Raises:
        ValidationError: If structure is invalid
    """
    if not isinstance(data, dict):
        raise ValidationError(
            "Data must be a dictionary/object",
            error_code="INVALID_DATA_TYPE",
            details={"expected_type": "dict", "actual_type": type(data).__name__}
        )

    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)

    if missing_fields:
        raise ValidationError(
            f"Missing required fields: {', '.join(missing_fields)}",
            error_code="MISSING_REQUIRED_FIELDS",
            details={"missing_fields": missing_fields, "required_fields": required_fields}
        )

    return data


def validate_enum_value(value: Any, enum_values: List[Any], field_name: str) -> Any:
    """
    Validate that value is in allowed enum values.

    Args:
        value: Value to validate
        enum_values: List of allowed values
        field_name: Name of the field

    Returns:
        Value if valid

    Raises:
        ValidationError: If value is not in enum
    """
    if value not in enum_values:
        raise ValidationError(
            f"{field_name} must be one of: {', '.join(map(str, enum_values))}",
            error_code="INVALID_ENUM_VALUE",
            details={
                "field_name": field_name,
                "value": value,
                "allowed_values": enum_values
            }
        )

    return value


# =============================================================================
# COMPOSITE VALIDATION FUNCTIONS
# =============================================================================

def validate_telegram_config(bot_token: str, chat_id: str) -> Tuple[str, str]:
    """
    Validate complete Telegram configuration.

    Args:
        bot_token: Telegram bot token
        chat_id: Telegram chat ID

    Returns:
        Tuple of (validated_token, validated_chat_id)

    Raises:
        ValidationError: If any validation fails
    """
    validated_token = validate_telegram_bot_token(bot_token)
    validated_chat_id = validate_telegram_chat_id(chat_id)

    return validated_token, validated_chat_id


def validate_file_upload(
    filename: str,
    size_bytes: int,
    allowed_extensions: List[str],
    max_size_bytes: int
) -> Tuple[str, int]:
    """
    Validate file upload parameters.

    Args:
        filename: Name of the uploaded file
        size_bytes: Size of the file in bytes
        allowed_extensions: List of allowed file extensions
        max_size_bytes: Maximum allowed file size

    Returns:
        Tuple of (validated_filename, validated_size)

    Raises:
        ValidationError: If any validation fails
    """
    validated_filename = validate_file_extension(filename, allowed_extensions)
    validated_size = validate_file_size(size_bytes, max_size_bytes)

    return validated_filename, validated_size


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def sanitize_string(value: str, max_length: int = None, allowed_chars: str = None) -> str:
    """
    Sanitize string by removing/replacing invalid characters.

    Args:
        value: String to sanitize
        max_length: Maximum length to truncate to
        allowed_chars: Regex pattern of allowed characters

    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        return str(value)

    # Remove control characters
    sanitized = ''.join(char for char in value if ord(char) >= 32 or char in '\t\n\r')

    # Apply character filter if provided
    if allowed_chars:
        sanitized = re.sub(f'[^{allowed_chars}]', '', sanitized)

    # Truncate if needed
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized.strip()


def generate_validation_hash(data: Dict[str, Any]) -> str:
    """
    Generate hash for data validation/integrity checking.

    Args:
        data: Data to hash

    Returns:
        SHA-256 hash of the data
    """
    import json

    # Sort keys for consistent hashing
    sorted_data = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(sorted_data.encode()).hexdigest()


if __name__ == "__main__":
    # Test validation functions
    try:
        print("Testing email validation...")
        validate_email("test@example.com")
        print("✅ Valid email passed")

        print("Testing Telegram token validation...")
        validate_telegram_bot_token("123456789:ABCdefGhIjKlMnOpQrStUvWxYz123456789")
        print("✅ Valid token passed")

        print("Testing file validation...")
        validate_file_upload("test.pdf", 1024000, ["pdf", "docx"], 5000000)
        print("✅ Valid file passed")

        print("All validation tests passed!")

    except ValidationError as e:
        print(f"❌ Validation failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")