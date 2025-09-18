"""
Custom exception classes for Telegram Assistant.
Provides specific exceptions for different error scenarios.
"""

from typing import Optional, Dict, Any


class TelegramAssistantException(Exception):
    """Base exception class for all Telegram Assistant errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/API responses."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details
        }


# =============================================================================
# CONFIGURATION ERRORS
# =============================================================================

class ConfigurationError(TelegramAssistantException):
    """Raised when configuration is invalid or missing."""
    pass


class MissingCredentialsError(ConfigurationError):
    """Raised when required API credentials are missing."""
    pass


# =============================================================================
# TELEGRAM ERRORS
# =============================================================================

class TelegramError(TelegramAssistantException):
    """Base class for Telegram-related errors."""
    pass


class TelegramAPIError(TelegramError):
    """Raised when Telegram API calls fail."""
    pass


class InvalidChatIdError(TelegramError):
    """Raised when chat ID is invalid or inaccessible."""
    pass


class WebhookError(TelegramError):
    """Raised when webhook configuration fails."""
    pass


# =============================================================================
# GOOGLE SERVICES ERRORS
# =============================================================================

class GoogleServiceError(TelegramAssistantException):
    """Base class for Google services errors."""
    pass


class GoogleDriveError(GoogleServiceError):
    """Raised when Google Drive operations fail."""
    pass


class GoogleDocsError(GoogleServiceError):
    """Raised when Google Docs operations fail."""
    pass


class GeminiAPIError(GoogleServiceError):
    """Raised when Google Gemini API calls fail."""
    pass


class ServiceAccountError(GoogleServiceError):
    """Raised when Google service account authentication fails."""
    pass


# =============================================================================
# FILE PROCESSING ERRORS
# =============================================================================

class FileProcessingError(TelegramAssistantException):
    """Base class for file processing errors."""
    pass


class UnsupportedFileTypeError(FileProcessingError):
    """Raised when file type is not supported."""
    pass


class FileSizeError(FileProcessingError):
    """Raised when file is too large to process."""
    pass


class FileDownloadError(FileProcessingError):
    """Raised when file download fails."""
    pass


class TextExtractionError(FileProcessingError):
    """Raised when text extraction from file fails."""
    pass


class ImageProcessingError(FileProcessingError):
    """Raised when image processing or OCR fails."""
    pass


class ExcelProcessingError(FileProcessingError):
    """Raised when Excel/CSV processing fails."""
    pass


# =============================================================================
# AI PROCESSING ERRORS
# =============================================================================

class AIProcessingError(TelegramAssistantException):
    """Base class for AI processing errors."""
    pass


class MetadataExtractionError(AIProcessingError):
    """Raised when AI metadata extraction fails."""
    pass


class EmbeddingGenerationError(AIProcessingError):
    """Raised when vector embedding generation fails."""
    pass


class ChatProcessingError(AIProcessingError):
    """Raised when chat processing fails."""
    pass


class MemoryError(AIProcessingError):
    """Raised when conversation memory operations fail."""
    pass


# =============================================================================
# VECTOR DATABASE ERRORS
# =============================================================================

class VectorDatabaseError(TelegramAssistantException):
    """Base class for vector database errors."""
    pass


class PineconeError(VectorDatabaseError):
    """Raised when Pinecone operations fail."""
    pass


class SupabaseError(VectorDatabaseError):
    """Raised when Supabase operations fail."""
    pass


class VectorSearchError(VectorDatabaseError):
    """Raised when vector search operations fail."""
    pass


class DocumentStorageError(VectorDatabaseError):
    """Raised when document storage operations fail."""
    pass


# =============================================================================
# DATABASE ERRORS
# =============================================================================

class DatabaseError(TelegramAssistantException):
    """Base class for database errors."""
    pass


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""
    pass


class QueryError(DatabaseError):
    """Raised when database queries fail."""
    pass


class MigrationError(DatabaseError):
    """Raised when database migrations fail."""
    pass


# =============================================================================
# WORKFLOW ERRORS
# =============================================================================

class WorkflowError(TelegramAssistantException):
    """Base class for workflow processing errors."""
    pass


class DocumentIngestionError(WorkflowError):
    """Raised when document ingestion workflow fails."""
    pass


class ChatWorkflowError(WorkflowError):
    """Raised when chat workflow processing fails."""
    pass


class ApprovalWorkflowError(WorkflowError):
    """Raised when approval workflow fails."""
    pass


class BatchProcessingError(WorkflowError):
    """Raised when batch processing fails."""
    pass


# =============================================================================
# HTTP AND API ERRORS
# =============================================================================

class HTTPError(TelegramAssistantException):
    """Base class for HTTP-related errors."""
    pass


class APIRequestError(HTTPError):
    """Raised when API requests fail."""
    pass


class RateLimitError(HTTPError):
    """Raised when API rate limits are exceeded."""
    pass


class AuthenticationError(HTTPError):
    """Raised when API authentication fails."""
    pass


# =============================================================================
# VALIDATION ERRORS
# =============================================================================

class ValidationError(TelegramAssistantException):
    """Base class for data validation errors."""
    pass


class InvalidDataError(ValidationError):
    """Raised when data doesn't meet validation requirements."""
    pass


class SchemaValidationError(ValidationError):
    """Raised when data doesn't match expected schema."""
    pass


# =============================================================================
# EXCEPTION UTILITIES
# =============================================================================

def handle_exception(
    exception: Exception,
    context: Optional[str] = None,
    reraise: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Handle and log exceptions in a standardized way.

    Args:
        exception: The exception to handle
        context: Additional context about where the error occurred
        reraise: Whether to re-raise the exception after handling

    Returns:
        Dictionary representation of the error if not re-raising
    """
    from .logger import get_logger

    logger = get_logger(__name__)

    # Convert to TelegramAssistantException if it's not already
    if not isinstance(exception, TelegramAssistantException):
        handled_exception = TelegramAssistantException(
            message=str(exception),
            error_code=exception.__class__.__name__,
            details={"original_type": type(exception).__name__}
        )
    else:
        handled_exception = exception

    # Add context if provided
    if context:
        handled_exception.details["context"] = context

    # Log the error
    error_dict = handled_exception.to_dict()
    logger.error(f"Exception handled: {error_dict}")

    if reraise:
        raise handled_exception
    else:
        return error_dict


def create_error_response(
    exception: TelegramAssistantException,
    include_details: bool = None
) -> Dict[str, Any]:
    """
    Create a standardized error response for API endpoints.

    Args:
        exception: The exception to convert
        include_details: Whether to include error details (auto-detected from environment)

    Returns:
        Dictionary suitable for API error response
    """
    from .config import settings

    if include_details is None:
        include_details = settings.is_development

    response = {
        "success": False,
        "error": {
            "type": exception.__class__.__name__,
            "message": exception.message,
            "code": exception.error_code
        }
    }

    if include_details and exception.details:
        response["error"]["details"] = exception.details

    return response


# =============================================================================
# EXCEPTION DECORATORS
# =============================================================================

def handle_exceptions(
    default_exception_class: type = TelegramAssistantException,
    context: Optional[str] = None
):
    """
    Decorator to automatically handle exceptions in functions.

    Args:
        default_exception_class: Exception class to use for unhandled exceptions
        context: Context string to add to error details
    """
    import functools

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except TelegramAssistantException:
                # Re-raise our custom exceptions as-is
                raise
            except Exception as e:
                # Convert other exceptions to our custom type
                raise default_exception_class(
                    message=f"Error in {func.__name__}: {str(e)}",
                    error_code=e.__class__.__name__,
                    details={"context": context, "function": func.__name__}
                )

        return wrapper
    return decorator


def handle_async_exceptions(
    default_exception_class: type = TelegramAssistantException,
    context: Optional[str] = None
):
    """
    Decorator to automatically handle exceptions in async functions.

    Args:
        default_exception_class: Exception class to use for unhandled exceptions
        context: Context string to add to error details
    """
    import functools

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except TelegramAssistantException:
                # Re-raise our custom exceptions as-is
                raise
            except Exception as e:
                # Convert other exceptions to our custom type
                raise default_exception_class(
                    message=f"Error in async {func.__name__}: {str(e)}",
                    error_code=e.__class__.__name__,
                    details={"context": context, "function": func.__name__}
                )

        return wrapper
    return decorator


if __name__ == "__main__":
    # Test exception handling
    try:
        raise FileProcessingError(
            "Test file processing error",
            error_code="TEST_001",
            details={"file_name": "test.pdf", "file_size": 1024}
        )
    except TelegramAssistantException as e:
        print("Exception details:", e.to_dict())
        print("Error response:", create_error_response(e))