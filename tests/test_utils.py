"""
Tests for utility functions and helper modules.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

from src.utils.file_utils import (
    is_supported_file_type, format_file_size, get_file_extension,
    validate_file_path, create_safe_filename
)
from src.utils.text_utils import (
    clean_text, count_words, extract_keywords, chunk_text,
    remove_html_tags, normalize_whitespace
)
from src.utils.validation_utils import (
    validate_email, validate_url, validate_phone_number,
    ValidationError, sanitize_input
)


class TestFileUtils:
    """Test file utility functions."""

    def test_is_supported_file_type(self):
        """Test file type validation."""
        # Supported types
        assert is_supported_file_type("document.pdf") is True
        assert is_supported_file_type("image.jpg") is True
        assert is_supported_file_type("spreadsheet.xlsx") is True
        assert is_supported_file_type("text.txt") is True
        assert is_supported_file_type("presentation.pptx") is True

        # Unsupported types
        assert is_supported_file_type("program.exe") is False
        assert is_supported_file_type("script.bat") is False
        assert is_supported_file_type("unknown.xyz") is False

        # Edge cases
        assert is_supported_file_type("") is False
        assert is_supported_file_type("no_extension") is False
        assert is_supported_file_type(".pdf") is True  # Extension only

    def test_format_file_size(self):
        """Test file size formatting."""
        # Bytes
        assert format_file_size(512) == "512 B"
        assert format_file_size(1023) == "1023 B"

        # Kilobytes
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1536) == "1.5 KB"

        # Megabytes
        assert format_file_size(1048576) == "1.0 MB"
        assert format_file_size(2097152) == "2.0 MB"

        # Gigabytes
        assert format_file_size(1073741824) == "1.0 GB"

        # Edge cases
        assert format_file_size(0) == "0 B"
        with pytest.raises(ValueError):
            format_file_size(-1)

    def test_get_file_extension(self):
        """Test file extension extraction."""
        assert get_file_extension("document.pdf") == "pdf"
        assert get_file_extension("image.JPG") == "jpg"  # Should be lowercase
        assert get_file_extension("archive.tar.gz") == "gz"  # Last extension
        assert get_file_extension("no_extension") == ""
        assert get_file_extension("") == ""

    def test_validate_file_path(self):
        """Test file path validation."""
        # Valid paths
        assert validate_file_path("/home/user/document.pdf") is True
        assert validate_file_path("./relative/path.txt") is True

        # Invalid paths (security)
        assert validate_file_path("../../../etc/passwd") is False
        assert validate_file_path("/etc/shadow") is False
        assert validate_file_path("C:\\Windows\\System32\\config") is False

        # Edge cases
        assert validate_file_path("") is False
        assert validate_file_path(None) is False

    def test_create_safe_filename(self):
        """Test safe filename creation."""
        # Normal filenames
        assert create_safe_filename("document.pdf") == "document.pdf"
        assert create_safe_filename("my file.txt") == "my_file.txt"

        # Special characters
        assert create_safe_filename("file/with\\invalid:chars?.pdf") == "file_with_invalid_chars_.pdf"
        assert create_safe_filename("très_intéressant.doc") == "tres_interessant.doc"

        # Edge cases
        assert create_safe_filename("") == "untitled"
        assert create_safe_filename("...") == "untitled"
        assert len(create_safe_filename("a" * 300)) <= 255  # Max filename length

    def test_file_utils_with_real_files(self, temp_text_file):
        """Test file utilities with real temporary files."""
        temp_path, content = temp_text_file

        # Test with actual file
        assert Path(temp_path).exists()
        assert is_supported_file_type(temp_path) is True

        file_size = os.path.getsize(temp_path)
        formatted_size = format_file_size(file_size)
        assert "B" in formatted_size or "KB" in formatted_size


class TestTextUtils:
    """Test text utility functions."""

    def test_clean_text(self, sample_text_data):
        """Test text cleaning functionality."""
        # Clean normal text
        clean = clean_text(sample_text_data["clean_text"])
        assert clean == sample_text_data["clean_text"]

        # Clean dirty text
        dirty = sample_text_data["dirty_text"]
        clean = clean_text(dirty)
        assert "   " not in clean  # No triple spaces
        assert "\n\n\n" not in clean  # No triple newlines
        assert not clean.startswith(" ")  # No leading whitespace
        assert not clean.endswith(" ")  # No trailing whitespace

    def test_count_words(self, sample_text_data):
        """Test word counting."""
        # Simple text
        count = count_words("Hello world")
        assert count == 2

        # Text with extra whitespace
        dirty_text = sample_text_data["dirty_text"]
        count = count_words(dirty_text)
        assert count > 0

        # Empty text
        assert count_words("") == 0
        assert count_words("   ") == 0

    def test_extract_keywords(self, sample_text_data):
        """Test keyword extraction."""
        text = "This is a test document about machine learning and artificial intelligence."
        keywords = extract_keywords(text, max_keywords=5)

        assert isinstance(keywords, list)
        assert len(keywords) <= 5
        assert all(isinstance(k, str) for k in keywords)

        # Empty text
        assert extract_keywords("") == []

    def test_chunk_text(self, sample_text_data):
        """Test text chunking."""
        long_text = sample_text_data["long_text"]
        chunks = chunk_text(long_text, chunk_size=100, overlap=20)

        assert isinstance(chunks, list)
        assert len(chunks) > 1
        assert all(len(chunk) <= 120 for chunk in chunks)  # chunk_size + overlap

        # Short text
        short_chunks = chunk_text("Short text", chunk_size=100)
        assert len(short_chunks) == 1

    def test_remove_html_tags(self, sample_text_data):
        """Test HTML tag removal."""
        html_text = sample_text_data["html_text"]
        clean_text = remove_html_tags(html_text)

        assert "<p>" not in clean_text
        assert "<strong>" not in clean_text
        assert "<em>" not in clean_text
        assert "HTML" in clean_text  # Content should remain
        assert "tags" in clean_text

    def test_normalize_whitespace(self, sample_text_data):
        """Test whitespace normalization."""
        dirty_text = sample_text_data["dirty_text"]
        normalized = normalize_whitespace(dirty_text)

        assert "  " not in normalized  # No double spaces
        assert "\n\n" not in normalized  # No double newlines
        assert not normalized.startswith(" ")
        assert not normalized.endswith(" ")

    def test_text_utils_edge_cases(self):
        """Test text utilities with edge cases."""
        # None input
        assert clean_text(None) == ""
        assert count_words(None) == 0

        # Unicode text
        unicode_text = "Café naïve résumé"
        cleaned = clean_text(unicode_text)
        assert "Café" in cleaned

        # Very long text
        long_text = "word " * 10000
        chunks = chunk_text(long_text, chunk_size=100)
        assert len(chunks) > 50


class TestValidationUtils:
    """Test validation utility functions."""

    def test_validate_email(self, sample_validation_data):
        """Test email validation."""
        # Valid email
        valid_email = sample_validation_data["valid_email"]
        assert validate_email(valid_email) == valid_email

        # Invalid emails
        invalid_emails = sample_validation_data["invalid_emails"]
        for invalid_email in invalid_emails:
            with pytest.raises(ValidationError):
                validate_email(invalid_email)

    def test_validate_url(self, sample_validation_data):
        """Test URL validation."""
        # Valid URLs
        valid_urls = sample_validation_data["valid_urls"]
        for valid_url in valid_urls:
            assert validate_url(valid_url) == valid_url

        # Invalid URLs
        invalid_urls = sample_validation_data["invalid_urls"]
        for invalid_url in invalid_urls:
            with pytest.raises(ValidationError):
                validate_url(invalid_url)

    def test_validate_phone_number(self, sample_validation_data):
        """Test phone number validation."""
        # Valid phone
        valid_phone = sample_validation_data["valid_phone"]
        normalized = validate_phone_number(valid_phone)
        assert isinstance(normalized, str)

        # Invalid phones
        invalid_phones = sample_validation_data["invalid_phones"]
        for invalid_phone in invalid_phones:
            with pytest.raises(ValidationError):
                validate_phone_number(invalid_phone)

    def test_sanitize_input(self):
        """Test input sanitization."""
        # Normal input
        safe_input = sanitize_input("Hello world")
        assert safe_input == "Hello world"

        # Input with special characters
        dangerous_input = "<script>alert('xss')</script>"
        safe_input = sanitize_input(dangerous_input)
        assert "<script>" not in safe_input

        # SQL injection attempt
        sql_input = "'; DROP TABLE users; --"
        safe_input = sanitize_input(sql_input)
        assert "DROP TABLE" not in safe_input

    def test_validation_error_handling(self):
        """Test validation error handling."""
        # Custom error message
        try:
            raise ValidationError("Custom error message", field="email")
        except ValidationError as e:
            assert str(e) == "Custom error message"
            assert e.field == "email"

        # Error without field
        try:
            raise ValidationError("General error")
        except ValidationError as e:
            assert e.field is None

    def test_validation_with_none_input(self):
        """Test validation functions with None input."""
        with pytest.raises(ValidationError):
            validate_email(None)

        with pytest.raises(ValidationError):
            validate_url(None)

        with pytest.raises(ValidationError):
            validate_phone_number(None)

        # Sanitize should handle None gracefully
        assert sanitize_input(None) == ""


class TestUtilsIntegration:
    """Test utility function integration scenarios."""

    def test_file_processing_pipeline(self, temp_text_file):
        """Test a complete file processing pipeline using utilities."""
        temp_path, content = temp_text_file

        # 1. Validate file type
        assert is_supported_file_type(temp_path) is True

        # 2. Get file info
        extension = get_file_extension(temp_path)
        file_size = os.path.getsize(temp_path)
        formatted_size = format_file_size(file_size)

        assert extension == "txt"
        assert "B" in formatted_size

        # 3. Process content
        cleaned_content = clean_text(content)
        word_count = count_words(cleaned_content)
        keywords = extract_keywords(cleaned_content)

        assert word_count > 0
        assert isinstance(keywords, list)

        # 4. Create safe filename for processed file
        safe_name = create_safe_filename(f"processed_{Path(temp_path).name}")
        assert safe_name.endswith(".txt")

    def test_text_processing_workflow(self, sample_text_data):
        """Test complete text processing workflow."""
        # Get mixed content (contains email, phone, etc.)
        mixed_content = sample_text_data["mixed_content"]

        # 1. Clean and normalize text
        cleaned = clean_text(mixed_content)
        normalized = normalize_whitespace(cleaned)

        # 2. Extract information
        word_count = count_words(normalized)
        keywords = extract_keywords(normalized)

        # 3. Chunk for processing
        chunks = chunk_text(normalized, chunk_size=50)

        # 4. Validate extracted data
        # (In real scenario, you'd extract emails/phones and validate them)

        assert word_count > 0
        assert len(keywords) >= 0
        assert len(chunks) >= 1
        assert all(len(chunk) <= 70 for chunk in chunks)  # chunk_size + overlap

    @pytest.mark.slow
    def test_large_file_processing(self):
        """Test utility functions with large data."""
        # Create large text
        large_text = "This is a test sentence. " * 10000

        # Test chunking performance
        chunks = chunk_text(large_text, chunk_size=1000)
        assert len(chunks) > 200

        # Test word counting performance
        word_count = count_words(large_text)
        assert word_count > 50000

        # Test cleaning performance
        cleaned = clean_text(large_text)
        assert len(cleaned) > 0

    def test_error_handling_across_utils(self):
        """Test error handling across all utility modules."""
        # File utils errors
        with pytest.raises(ValueError):
            format_file_size(-100)

        # Text utils with problematic input
        assert clean_text("") == ""
        assert count_words("") == 0

        # Validation utils errors
        with pytest.raises(ValidationError):
            validate_email("invalid")

        # All utilities should handle None gracefully or raise appropriate errors
        assert clean_text(None) == ""
        assert sanitize_input(None) == ""