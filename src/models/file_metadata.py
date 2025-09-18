"""
File metadata model for tracking file processing status and information.
Supports the file monitoring and processing pipeline from the n8n workflow.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Text, JSON, Boolean, Float
from pydantic import BaseModel, Field, validator
from enum import Enum

from ..core.database import Base


# =============================================================================
# Enums
# =============================================================================

class FileStatus(str, Enum):
    """File processing status enumeration."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class FileSource(str, Enum):
    """File source enumeration."""
    GOOGLE_DRIVE = "google_drive"
    TELEGRAM = "telegram"
    UPLOAD = "upload"
    URL = "url"


# =============================================================================
# SQLAlchemy ORM Model
# =============================================================================

class FileMetadata(Base):
    """File metadata model for tracking files through the processing pipeline."""

    __tablename__ = "file_metadata"

    # File identification
    file_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))

    # File properties
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)  # SHA-256 hash

    # Source information
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="google_drive")  # google_drive, telegram, upload
    source_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)  # Google Drive ID, Telegram file ID, etc.
    source_path: Mapped[Optional[str]] = mapped_column(String(1000))  # Full path or URL

    # Google Drive specific
    google_drive_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    google_drive_folder_id: Mapped[Optional[str]] = mapped_column(String(255))
    google_drive_modified_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    google_drive_shared: Mapped[Optional[bool]] = mapped_column(Boolean)

    # Processing status
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    processing_duration_seconds: Mapped[Optional[float]] = mapped_column(Float)

    # Processing results
    text_extracted: Mapped[bool] = mapped_column(Boolean, default=False)
    text_length: Mapped[Optional[int]] = mapped_column(Integer)
    ai_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    vector_stored: Mapped[bool] = mapped_column(Boolean, default=False)

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_code: Mapped[Optional[str]] = mapped_column(String(100))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # Content analysis
    detected_language: Mapped[Optional[str]] = mapped_column(String(10))
    content_type: Mapped[Optional[str]] = mapped_column(String(100))  # document, image, spreadsheet, etc.

    # Relationships and references
    document_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)  # Reference to Document table
    parent_file_id: Mapped[Optional[str]] = mapped_column(String(255))  # For files created from other files

    # Processing metadata
    processing_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    extraction_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    # Tags and categorization
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON)
    category: Mapped[Optional[str]] = mapped_column(String(100))

    # Monitoring and metrics
    download_time_seconds: Mapped[Optional[float]] = mapped_column(Float)
    extraction_time_seconds: Mapped[Optional[float]] = mapped_column(Float)
    ai_processing_time_seconds: Mapped[Optional[float]] = mapped_column(Float)

    def __repr__(self):
        return f"<FileMetadata(id={self.id}, file_id='{self.file_id}', status='{self.status}')>"

    @property
    def is_processing(self) -> bool:
        """Check if file is currently being processed."""
        return self.status in [FileStatus.DOWNLOADING, FileStatus.PROCESSING]

    @property
    def is_completed(self) -> bool:
        """Check if file processing is completed."""
        return self.status == FileStatus.COMPLETED

    @property
    def has_failed(self) -> bool:
        """Check if file processing has failed."""
        return self.status == FileStatus.FAILED

    @property
    def can_retry(self) -> bool:
        """Check if file processing can be retried."""
        return self.has_failed and self.retry_count < self.max_retries


# =============================================================================
# Pydantic Schemas
# =============================================================================

class FileMetadataBase(BaseModel):
    """Base schema for FileMetadata with common fields."""

    file_id: str = Field(..., description="Unique file identifier")
    original_filename: str = Field(..., description="Original filename")
    file_extension: str = Field(..., description="File extension")
    mime_type: Optional[str] = Field(None, description="MIME type")
    file_size_bytes: int = Field(..., gt=0, description="File size in bytes")
    file_hash: Optional[str] = Field(None, description="SHA-256 hash of file")

    source: str = Field(default="google_drive", description="File source")
    source_id: Optional[str] = Field(None, description="Source-specific ID")
    source_path: Optional[str] = Field(None, description="Source path or URL")

    google_drive_id: Optional[str] = Field(None, description="Google Drive file ID")
    google_drive_folder_id: Optional[str] = Field(None, description="Google Drive folder ID")
    google_drive_modified_time: Optional[datetime] = Field(None, description="Google Drive modification time")
    google_drive_shared: Optional[bool] = Field(None, description="Whether file is shared")

    status: str = Field(default="pending", description="Processing status")
    processing_started_at: Optional[datetime] = Field(None, description="Processing start time")
    processing_completed_at: Optional[datetime] = Field(None, description="Processing completion time")
    processing_duration_seconds: Optional[float] = Field(None, ge=0, description="Processing duration")

    text_extracted: bool = Field(default=False, description="Whether text was extracted")
    text_length: Optional[int] = Field(None, ge=0, description="Length of extracted text")
    ai_processed: bool = Field(default=False, description="Whether AI processing completed")
    vector_stored: bool = Field(default=False, description="Whether stored in vector DB")

    error_message: Optional[str] = Field(None, description="Error message if failed")
    error_code: Optional[str] = Field(None, description="Error code if failed")
    retry_count: int = Field(default=0, ge=0, description="Number of processing retries")
    max_retries: int = Field(default=3, ge=0, description="Maximum allowed retries")

    detected_language: Optional[str] = Field(None, description="Detected content language")
    content_type: Optional[str] = Field(None, description="Content type classification")

    document_id: Optional[int] = Field(None, description="Associated document ID")
    parent_file_id: Optional[str] = Field(None, description="Parent file ID if derived")

    processing_metadata: Optional[Dict[str, Any]] = Field(None, description="Processing metadata")
    extraction_metadata: Optional[Dict[str, Any]] = Field(None, description="Extraction metadata")

    tags: Optional[List[str]] = Field(None, description="File tags")
    category: Optional[str] = Field(None, description="File category")

    download_time_seconds: Optional[float] = Field(None, ge=0, description="Download time")
    extraction_time_seconds: Optional[float] = Field(None, ge=0, description="Text extraction time")
    ai_processing_time_seconds: Optional[float] = Field(None, ge=0, description="AI processing time")

    @validator("file_extension")
    def validate_file_extension(cls, v):
        """Clean up file extension."""
        if v:
            return v.lower().strip('.')
        return v

    @validator("status")
    def validate_status(cls, v):
        """Validate status enum."""
        if v not in [status.value for status in FileStatus]:
            raise ValueError(f"status must be one of: {[s.value for s in FileStatus]}")
        return v

    @validator("source")
    def validate_source(cls, v):
        """Validate source enum."""
        if v not in [source.value for source in FileSource]:
            raise ValueError(f"source must be one of: {[s.value for s in FileSource]}")
        return v

    @validator("tags")
    def validate_tags(cls, v):
        """Clean up tags list."""
        if v:
            return [tag.strip() for tag in v if tag and tag.strip()]
        return v


class FileMetadataCreate(FileMetadataBase):
    """Schema for creating file metadata."""
    pass


class FileMetadataUpdate(BaseModel):
    """Schema for updating file metadata."""

    status: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_duration_seconds: Optional[float] = None

    text_extracted: Optional[bool] = None
    text_length: Optional[int] = None
    ai_processed: Optional[bool] = None
    vector_stored: Optional[bool] = None

    error_message: Optional[str] = None
    error_code: Optional[str] = None
    retry_count: Optional[int] = None

    detected_language: Optional[str] = None
    content_type: Optional[str] = None
    document_id: Optional[int] = None

    processing_metadata: Optional[Dict[str, Any]] = None
    extraction_metadata: Optional[Dict[str, Any]] = None

    tags: Optional[List[str]] = None
    category: Optional[str] = None

    download_time_seconds: Optional[float] = None
    extraction_time_seconds: Optional[float] = None
    ai_processing_time_seconds: Optional[float] = None

    @validator("status")
    def validate_status(cls, v):
        """Validate status enum."""
        if v is not None and v not in [status.value for status in FileStatus]:
            raise ValueError(f"status must be one of: {[s.value for s in FileStatus]}")
        return v


class FileMetadataResponse(FileMetadataBase):
    """Schema for file metadata API responses."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FileProcessingStats(BaseModel):
    """File processing statistics."""

    total_files: int
    by_status: Dict[str, int]
    by_source: Dict[str, int]
    by_file_type: Dict[str, int]
    processing_metrics: Dict[str, float]
    error_summary: Dict[str, int]


class FileSearchQuery(BaseModel):
    """Schema for searching files."""

    filename: Optional[str] = Field(None, description="Search by filename")
    file_extension: Optional[str] = Field(None, description="Filter by file extension")
    source: Optional[str] = Field(None, description="Filter by source")
    status: Optional[str] = Field(None, description="Filter by status")
    category: Optional[str] = Field(None, description="Filter by category")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    date_from: Optional[datetime] = Field(None, description="Filter from date")
    date_to: Optional[datetime] = Field(None, description="Filter to date")
    limit: int = Field(default=50, ge=1, le=500, description="Maximum results")

    @validator("status")
    def validate_status(cls, v):
        """Validate status filter."""
        if v and v not in [status.value for status in FileStatus]:
            raise ValueError(f"status must be one of: {[s.value for s in FileStatus]}")
        return v

    @validator("source")
    def validate_source(cls, v):
        """Validate source filter."""
        if v and v not in [source.value for source in FileSource]:
            raise ValueError(f"source must be one of: {[s.value for s in FileSource]}")
        return v


# =============================================================================
# Utility Functions
# =============================================================================

def create_file_metadata_from_google_drive(
    drive_file: Dict[str, Any],
    folder_id: str = None
) -> FileMetadataCreate:
    """
    Create FileMetadata from Google Drive file information.

    Args:
        drive_file: Google Drive file metadata
        folder_id: Google Drive folder ID

    Returns:
        FileMetadataCreate instance
    """
    filename = drive_file.get("name", "unknown")
    file_extension = filename.split('.')[-1].lower() if '.' in filename else ""

    return FileMetadataCreate(
        file_id=f"gdrive_{drive_file['id']}",
        original_filename=filename,
        file_extension=file_extension,
        mime_type=drive_file.get("mimeType"),
        file_size_bytes=int(drive_file.get("size", 0)),
        source="google_drive",
        source_id=drive_file["id"],
        google_drive_id=drive_file["id"],
        google_drive_folder_id=folder_id,
        google_drive_modified_time=datetime.fromisoformat(
            drive_file["modifiedTime"].replace("Z", "+00:00")
        ) if drive_file.get("modifiedTime") else None
    )


def create_processing_update(
    status: FileStatus,
    error_message: str = None,
    error_code: str = None,
    processing_time: float = None,
    metadata: Dict[str, Any] = None
) -> FileMetadataUpdate:
    """
    Create a processing status update.

    Args:
        status: New processing status
        error_message: Error message if failed
        error_code: Error code if failed
        processing_time: Processing duration
        metadata: Additional metadata

    Returns:
        FileMetadataUpdate instance
    """
    update_data = {
        "status": status.value,
        "processing_metadata": metadata
    }

    if status == FileStatus.PROCESSING:
        update_data["processing_started_at"] = datetime.utcnow()
    elif status in [FileStatus.COMPLETED, FileStatus.FAILED]:
        update_data["processing_completed_at"] = datetime.utcnow()
        if processing_time:
            update_data["processing_duration_seconds"] = processing_time

    if error_message:
        update_data["error_message"] = error_message
    if error_code:
        update_data["error_code"] = error_code

    return FileMetadataUpdate(**update_data)


def get_supported_file_types() -> List[str]:
    """Get list of supported file types."""
    return [
        "pdf", "docx", "doc", "txt", "rtf",
        "xlsx", "xls", "csv",
        "jpg", "jpeg", "png", "gif", "webp", "tiff",
        "pptx", "ppt"
    ]


def is_supported_file_type(file_extension: str) -> bool:
    """
    Check if file type is supported for processing.

    Args:
        file_extension: File extension to check

    Returns:
        bool: True if supported
    """
    return file_extension.lower().strip('.') in get_supported_file_types()


def calculate_file_hash(file_path: str) -> str:
    """
    Calculate SHA-256 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        str: SHA-256 hash
    """
    import hashlib

    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()