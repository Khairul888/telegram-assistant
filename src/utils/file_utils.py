"""
File handling utilities for Telegram Assistant.
Provides common file operations, validation, and processing helpers.
"""

import os
import hashlib
import mimetypes
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import tempfile
import aiofiles
import asyncio
from datetime import datetime

from ..core.config import settings
from ..core.logger import get_logger
from ..core.exceptions import (
    FileProcessingError,
    FileSizeError,
    UnsupportedFileTypeError,
    FileDownloadError
)

logger = get_logger(__name__)


# =============================================================================
# FILE VALIDATION
# =============================================================================

def get_file_extension(filename: str) -> str:
    """
    Get file extension from filename.

    Args:
        filename: Name of the file

    Returns:
        File extension (lowercase, without dot)
    """
    if not filename or '.' not in filename:
        return ""

    return filename.split('.')[-1].lower()


def get_mime_type(filename: str) -> str:
    """
    Get MIME type from filename.

    Args:
        filename: Name of the file

    Returns:
        MIME type string
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def is_supported_file_type(filename: str) -> bool:
    """
    Check if file type is supported for processing.

    Args:
        filename: Name of the file

    Returns:
        True if file type is supported
    """
    extension = get_file_extension(filename)
    return extension in settings.supported_file_types


def validate_file_size(file_size_bytes: int) -> bool:
    """
    Validate file size against maximum allowed size.

    Args:
        file_size_bytes: Size of file in bytes

    Returns:
        True if file size is acceptable

    Raises:
        FileSizeError: If file is too large
    """
    if file_size_bytes > settings.max_file_size_bytes:
        raise FileSizeError(
            f"File size {file_size_bytes} bytes exceeds maximum allowed size {settings.max_file_size_bytes} bytes",
            error_code="FILE_TOO_LARGE",
            details={
                "file_size_bytes": file_size_bytes,
                "max_size_bytes": settings.max_file_size_bytes,
                "max_size_mb": settings.max_file_size_mb
            }
        )
    return True


def validate_filename(filename: str) -> bool:
    """
    Validate filename for security and compatibility.

    Args:
        filename: Name of the file

    Returns:
        True if filename is valid

    Raises:
        FileProcessingError: If filename is invalid
    """
    if not filename or not filename.strip():
        raise FileProcessingError(
            "Filename cannot be empty",
            error_code="INVALID_FILENAME"
        )

    # Check for dangerous characters
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\0']
    for char in dangerous_chars:
        if char in filename:
            raise FileProcessingError(
                f"Filename contains invalid character: {char}",
                error_code="INVALID_FILENAME_CHAR",
                details={"filename": filename, "invalid_char": char}
            )

    # Check length
    if len(filename) > 255:
        raise FileProcessingError(
            "Filename too long (max 255 characters)",
            error_code="FILENAME_TOO_LONG",
            details={"filename": filename, "length": len(filename)}
        )

    return True


# =============================================================================
# FILE OPERATIONS
# =============================================================================

async def calculate_file_hash(file_path: str, algorithm: str = "sha256") -> str:
    """
    Calculate hash of a file asynchronously.

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (sha256, md5, etc.)

    Returns:
        Hex digest of the file hash

    Raises:
        FileProcessingError: If file cannot be read
    """
    try:
        hash_obj = hashlib.new(algorithm)

        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                hash_obj.update(chunk)

        return hash_obj.hexdigest()

    except Exception as e:
        logger.error(f"Failed to calculate file hash: {e}")
        raise FileProcessingError(
            f"Failed to calculate file hash: {str(e)}",
            error_code="HASH_CALCULATION_FAILED",
            details={"file_path": file_path, "algorithm": algorithm}
        )


async def get_file_info(file_path: str) -> Dict[str, Any]:
    """
    Get comprehensive information about a file.

    Args:
        file_path: Path to the file

    Returns:
        Dictionary with file information
    """
    try:
        path = Path(file_path)

        if not path.exists():
            raise FileProcessingError(
                f"File not found: {file_path}",
                error_code="FILE_NOT_FOUND"
            )

        stat_info = path.stat()

        return {
            "filename": path.name,
            "file_extension": get_file_extension(path.name),
            "mime_type": get_mime_type(path.name),
            "size_bytes": stat_info.st_size,
            "created_at": datetime.fromtimestamp(stat_info.st_ctime),
            "modified_at": datetime.fromtimestamp(stat_info.st_mtime),
            "is_file": path.is_file(),
            "is_directory": path.is_dir(),
            "absolute_path": str(path.absolute()),
            "file_hash": await calculate_file_hash(file_path)
        }

    except Exception as e:
        logger.error(f"Failed to get file info: {e}")
        raise FileProcessingError(
            f"Failed to get file info: {str(e)}",
            error_code="FILE_INFO_FAILED",
            details={"file_path": file_path}
        )


async def create_temp_file(content: bytes = None, suffix: str = None) -> str:
    """
    Create a temporary file.

    Args:
        content: Optional content to write to file
        suffix: Optional file suffix

    Returns:
        Path to the temporary file
    """
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            if content:
                tmp_file.write(content)
            return tmp_file.name

    except Exception as e:
        logger.error(f"Failed to create temp file: {e}")
        raise FileProcessingError(
            f"Failed to create temp file: {str(e)}",
            error_code="TEMP_FILE_CREATION_FAILED"
        )


async def cleanup_temp_file(file_path: str) -> bool:
    """
    Clean up a temporary file.

    Args:
        file_path: Path to the temporary file

    Returns:
        True if file was deleted successfully
    """
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.debug(f"Cleaned up temp file: {file_path}")
            return True
        return False

    except Exception as e:
        logger.warning(f"Failed to cleanup temp file {file_path}: {e}")
        return False


async def safe_file_operation(operation, *args, **kwargs):
    """
    Execute a file operation with error handling and cleanup.

    Args:
        operation: Async function to execute
        *args: Arguments for the operation
        **kwargs: Keyword arguments for the operation

    Returns:
        Result of the operation
    """
    temp_files = []
    try:
        result = await operation(*args, **kwargs)

        # Extract temp files from result if it's a dict with 'temp_files' key
        if isinstance(result, dict) and 'temp_files' in result:
            temp_files.extend(result['temp_files'])

        return result

    except Exception as e:
        logger.error(f"File operation failed: {e}")
        raise

    finally:
        # Clean up any temporary files
        for temp_file in temp_files:
            await cleanup_temp_file(temp_file)


# =============================================================================
# FILE CONTENT UTILITIES
# =============================================================================

async def read_text_file(file_path: str, encoding: str = "utf-8") -> str:
    """
    Read text content from a file.

    Args:
        file_path: Path to the file
        encoding: Text encoding (default utf-8)

    Returns:
        File content as string

    Raises:
        FileProcessingError: If file cannot be read
    """
    try:
        async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
            content = await f.read()
            return content

    except UnicodeDecodeError as e:
        # Try with different encodings
        for fallback_encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
            try:
                async with aiofiles.open(file_path, 'r', encoding=fallback_encoding) as f:
                    content = await f.read()
                    logger.warning(f"Used fallback encoding {fallback_encoding} for {file_path}")
                    return content
            except UnicodeDecodeError:
                continue

        raise FileProcessingError(
            f"Failed to decode text file with any encoding: {str(e)}",
            error_code="TEXT_DECODE_FAILED",
            details={"file_path": file_path, "attempted_encoding": encoding}
        )

    except Exception as e:
        logger.error(f"Failed to read text file: {e}")
        raise FileProcessingError(
            f"Failed to read text file: {str(e)}",
            error_code="TEXT_READ_FAILED",
            details={"file_path": file_path, "encoding": encoding}
        )


async def write_text_file(file_path: str, content: str, encoding: str = "utf-8") -> bool:
    """
    Write text content to a file.

    Args:
        file_path: Path to the file
        content: Text content to write
        encoding: Text encoding (default utf-8)

    Returns:
        True if successful

    Raises:
        FileProcessingError: If file cannot be written
    """
    try:
        # Create directory if it doesn't exist
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(file_path, 'w', encoding=encoding) as f:
            await f.write(content)

        logger.debug(f"Successfully wrote text file: {file_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to write text file: {e}")
        raise FileProcessingError(
            f"Failed to write text file: {str(e)}",
            error_code="TEXT_WRITE_FAILED",
            details={"file_path": file_path, "encoding": encoding}
        )


async def copy_file(source_path: str, dest_path: str) -> bool:
    """
    Copy a file asynchronously.

    Args:
        source_path: Source file path
        dest_path: Destination file path

    Returns:
        True if successful

    Raises:
        FileProcessingError: If copy fails
    """
    try:
        # Create destination directory if needed
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(source_path, 'rb') as src:
            async with aiofiles.open(dest_path, 'wb') as dst:
                while chunk := await src.read(8192):
                    await dst.write(chunk)

        logger.debug(f"Successfully copied file: {source_path} -> {dest_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to copy file: {e}")
        raise FileProcessingError(
            f"Failed to copy file: {str(e)}",
            error_code="FILE_COPY_FAILED",
            details={"source_path": source_path, "dest_path": dest_path}
        )


# =============================================================================
# FILE FILTERING AND SEARCHING
# =============================================================================

def filter_files_by_type(files: List[str], file_types: List[str]) -> List[str]:
    """
    Filter files by their extensions.

    Args:
        files: List of file paths/names
        file_types: List of file extensions to include

    Returns:
        Filtered list of files
    """
    if not file_types:
        return files

    file_types = [ext.lower().strip('.') for ext in file_types]
    filtered = []

    for file_path in files:
        extension = get_file_extension(file_path)
        if extension in file_types:
            filtered.append(file_path)

    return filtered


def sort_files_by_date(files: List[str], reverse: bool = True) -> List[str]:
    """
    Sort files by modification date.

    Args:
        files: List of file paths
        reverse: If True, newest first

    Returns:
        Sorted list of files
    """
    def get_mtime(file_path):
        try:
            return os.path.getmtime(file_path)
        except OSError:
            return 0

    return sorted(files, key=get_mtime, reverse=reverse)


# =============================================================================
# FILE SIZE UTILITIES
# =============================================================================

def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string (e.g., "1.5 MB")
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)

    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1

    return f"{size:.1f} {size_names[i]}"


def parse_file_size(size_string: str) -> int:
    """
    Parse human-readable file size to bytes.

    Args:
        size_string: Size string (e.g., "1.5 MB")

    Returns:
        Size in bytes
    """
    size_string = size_string.upper().strip()

    multipliers = {
        'B': 1,
        'KB': 1024,
        'MB': 1024 ** 2,
        'GB': 1024 ** 3,
        'TB': 1024 ** 4
    }

    for suffix, multiplier in multipliers.items():
        if size_string.endswith(suffix):
            number = float(size_string[:-len(suffix)].strip())
            return int(number * multiplier)

    # If no suffix, assume bytes
    try:
        return int(float(size_string))
    except ValueError:
        raise ValueError(f"Invalid file size format: {size_string}")


# =============================================================================
# BATCH FILE OPERATIONS
# =============================================================================

async def process_files_batch(
    file_paths: List[str],
    processor_func,
    batch_size: int = 5,
    *args,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Process multiple files in batches.

    Args:
        file_paths: List of file paths to process
        processor_func: Async function to process each file
        batch_size: Number of files to process concurrently
        *args: Additional args for processor function
        **kwargs: Additional kwargs for processor function

    Returns:
        List of processing results
    """
    results = []

    for i in range(0, len(file_paths), batch_size):
        batch = file_paths[i:i + batch_size]

        # Process batch concurrently
        tasks = [
            processor_func(file_path, *args, **kwargs)
            for file_path in batch
        ]

        try:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for file_path, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to process {file_path}: {result}")
                    results.append({
                        "file_path": file_path,
                        "success": False,
                        "error": str(result)
                    })
                else:
                    results.append({
                        "file_path": file_path,
                        "success": True,
                        "result": result
                    })

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            for file_path in batch:
                results.append({
                    "file_path": file_path,
                    "success": False,
                    "error": str(e)
                })

    return results


if __name__ == "__main__":
    # Test utilities
    import asyncio

    async def test_file_utils():
        # Test file validation
        print("Testing file validation...")
        print(f"PDF supported: {is_supported_file_type('test.pdf')}")
        print(f"EXE supported: {is_supported_file_type('test.exe')}")

        # Test size formatting
        print(f"Format 1024 bytes: {format_file_size(1024)}")
        print(f"Format 1.5 MB: {parse_file_size('1.5 MB')} bytes")

    asyncio.run(test_file_utils())