"""
Logging configuration for Telegram Assistant.
Provides structured logging with different levels and outputs.
"""

import logging
import sys
from typing import Optional
from pathlib import Path
from loguru import logger
from datetime import datetime

from .config import settings


class InterceptHandler(logging.Handler):
    """Intercept standard logging messages toward loguru."""

    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None
) -> None:
    """
    Configure application logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
    """
    # Use config log level if not specified
    if log_level is None:
        log_level = settings.log_level.upper()

    # Remove default loguru handler
    logger.remove()

    # Format configuration
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Add console handler
    logger.add(
        sys.stdout,
        format=log_format,
        level=log_level,
        colorize=True,
        backtrace=True,
        diagnose=True
    )

    # Add file handler if specified or in production
    if log_file or settings.is_production:
        if not log_file:
            # Default log file path
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / f"telegram_assistant_{datetime.now().strftime('%Y%m%d')}.log"

        logger.add(
            log_file,
            format=log_format,
            level=log_level,
            rotation="1 day",
            retention="30 days",
            compression="zip",
            backtrace=True,
            diagnose=True
        )

    # Intercept standard library logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Configure specific loggers
    configure_external_loggers()

    logger.info(f"Logging configured - Level: {log_level}, Environment: {settings.environment}")


def configure_external_loggers():
    """Configure logging for external libraries."""

    # Reduce noise from external libraries
    external_loggers = [
        "httpx",
        "httpcore",
        "telegram",
        "google",
        "pinecone",
        "supabase",
        "asyncio",
        "uvicorn.access"
    ]

    for logger_name in external_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Set specific levels for important loggers
    if settings.is_development:
        logging.getLogger("telegram").setLevel(logging.INFO)
        logging.getLogger("src").setLevel(logging.DEBUG)
    else:
        logging.getLogger("uvicorn").setLevel(logging.INFO)


def get_logger(name: str) -> "logger":
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logger.bind(name=name)


# =============================================================================
# LOGGING UTILITIES
# =============================================================================

def log_function_call(func):
    """Decorator to log function calls with parameters and execution time."""
    import functools
    import time

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        func_logger = get_logger(func.__module__)
        start_time = time.time()

        # Log function call (only in debug mode)
        if settings.debug:
            func_logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")

        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time

            if settings.debug:
                func_logger.debug(f"{func.__name__} completed in {execution_time:.3f}s")

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            func_logger.error(
                f"{func.__name__} failed after {execution_time:.3f}s: {str(e)}"
            )
            raise

    return wrapper


def log_async_function_call(func):
    """Decorator to log async function calls with parameters and execution time."""
    import functools
    import time
    import asyncio

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        func_logger = get_logger(func.__module__)
        start_time = time.time()

        # Log function call (only in debug mode)
        if settings.debug:
            func_logger.debug(f"Calling async {func.__name__} with args={args}, kwargs={kwargs}")

        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time

            if settings.debug:
                func_logger.debug(f"Async {func.__name__} completed in {execution_time:.3f}s")

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            func_logger.error(
                f"Async {func.__name__} failed after {execution_time:.3f}s: {str(e)}"
            )
            raise

    return wrapper


# =============================================================================
# CONTEXT MANAGERS FOR LOGGING
# =============================================================================

class LogContext:
    """Context manager for logging operations with automatic success/failure logging."""

    def __init__(self, operation_name: str, logger_instance=None):
        self.operation_name = operation_name
        self.logger = logger_instance or logger
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        self.logger.info(f"Starting operation: {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        execution_time = time.time() - self.start_time

        if exc_type is None:
            self.logger.info(
                f"Operation '{self.operation_name}' completed successfully in {execution_time:.3f}s"
            )
        else:
            self.logger.error(
                f"Operation '{self.operation_name}' failed after {execution_time:.3f}s: {exc_val}"
            )

        return False  # Don't suppress exceptions


# =============================================================================
# INITIALIZATION
# =============================================================================

# Setup logging when module is imported
setup_logging()

# Create module logger
module_logger = get_logger(__name__)
module_logger.info("Logging system initialized")


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Test logging setup
    test_logger = get_logger(__name__)

    test_logger.debug("This is a debug message")
    test_logger.info("This is an info message")
    test_logger.warning("This is a warning message")
    test_logger.error("This is an error message")

    # Test context manager
    with LogContext("test operation", test_logger):
        import time
        time.sleep(0.1)
        test_logger.info("Doing some work...")

    # Test decorator
    @log_function_call
    def test_function(x, y):
        return x + y

    result = test_function(1, 2)
    test_logger.info(f"Function result: {result}")