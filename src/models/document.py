"""
Document model for storing processed files and their metadata.
Replicates the document storage functionality from the n8n workflow.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Text, JSON, Float, Boolean
from pydantic import BaseModel, Field, validator

from ..core.database import Base


# =============================================================================
# SQLAlchemy ORM Model
# =============================================================================

class Document(Base):
    """Document model for storing processed files and their AI-extracted metadata."""

    __tablename__ = "documents"

    # File identification
    file_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # pdf, docx, txt, jpg, etc.
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))

    # Google Drive metadata
    google_drive_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    google_drive_folder_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Content and processing
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)
    processing_status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, processing, completed, failed
    processing_error: Mapped[Optional[str]] = mapped_column(Text)

    # AI-extracted metadata (from n8n workflow)
    overarching_theme: Mapped[Optional[str]] = mapped_column(Text)
    recurring_topics: Mapped[Optional[List[str]]] = mapped_column(JSON)  # Array of topics
    pain_points: Mapped[Optional[List[str]]] = mapped_column(JSON)  # Array of pain points
    analytical_insights: Mapped[Optional[str]] = mapped_column(Text)
    conclusion: Mapped[Optional[str]] = mapped_column(Text)
    keywords: Mapped[Optional[List[str]]] = mapped_column(JSON)  # Array of keywords

    # Vector storage information
    vector_stored: Mapped[bool] = mapped_column(Boolean, default=False)
    vector_id: Mapped[Optional[str]] = mapped_column(String(255))  # ID in Pinecone/Supabase
    embedding_model: Mapped[Optional[str]] = mapped_column(String(100))  # Model used for embeddings

    # Processing metrics
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    processing_time_seconds: Mapped[Optional[float]] = mapped_column(Float)
    chunk_count: Mapped[Optional[int]] = mapped_column(Integer)

    # Additional metadata
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)  # Flexible additional data
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON)  # User-defined tags

    def __repr__(self):
        return f"<Document(id={self.id}, file_id='{self.file_id}', filename='{self.original_filename}')>"


# =============================================================================
# Pydantic Schemas
# =============================================================================

class DocumentBase(BaseModel):
    """Base schema for Document with common fields."""

    file_id: str = Field(..., description="Unique identifier for the file")
    original_filename: str = Field(..., description="Original name of the file")
    file_type: str = Field(..., description="File extension (pdf, docx, txt, etc.)")
    file_size_bytes: int = Field(..., gt=0, description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type of the file")

    google_drive_id: Optional[str] = Field(None, description="Google Drive file ID")
    google_drive_folder_id: Optional[str] = Field(None, description="Google Drive folder ID")

    extracted_text: Optional[str] = Field(None, description="Extracted text content")
    processing_status: str = Field(default="pending", description="Processing status")

    # AI metadata
    overarching_theme: Optional[str] = Field(None, description="Main theme of the document")
    recurring_topics: Optional[List[str]] = Field(None, description="List of recurring topics")
    pain_points: Optional[List[str]] = Field(None, description="List of identified pain points")
    analytical_insights: Optional[str] = Field(None, description="AI-generated insights")
    conclusion: Optional[str] = Field(None, description="Summary conclusion")
    keywords: Optional[List[str]] = Field(None, description="Extracted keywords")

    # Vector storage
    vector_stored: bool = Field(default=False, description="Whether document is stored in vector DB")
    vector_id: Optional[str] = Field(None, description="Vector database ID")
    embedding_model: Optional[str] = Field(None, description="Embedding model used")

    # Processing metrics
    token_count: Optional[int] = Field(None, ge=0, description="Number of tokens processed")
    processing_time_seconds: Optional[float] = Field(None, ge=0, description="Processing time")
    chunk_count: Optional[int] = Field(None, ge=0, description="Number of chunks created")

    metadata_json: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    tags: Optional[List[str]] = Field(None, description="User-defined tags")

    @validator("file_type")
    def validate_file_type(cls, v):
        """Ensure file type is lowercase and clean."""
        if v:
            return v.lower().strip('.')
        return v

    @validator("processing_status")
    def validate_processing_status(cls, v):
        """Validate processing status values."""
        valid_statuses = ["pending", "processing", "completed", "failed", "skipped"]
        if v not in valid_statuses:
            raise ValueError(f"processing_status must be one of: {valid_statuses}")
        return v

    @validator("keywords", "recurring_topics", "pain_points", "tags")
    def validate_string_lists(cls, v):
        """Clean up string lists - remove empty strings and duplicates."""
        if v:
            # Remove empty strings and duplicates while preserving order
            cleaned = []
            for item in v:
                if item and item.strip() and item not in cleaned:
                    cleaned.append(item.strip())
            return cleaned
        return v


class DocumentCreate(DocumentBase):
    """Schema for creating a new document."""
    pass


class DocumentUpdate(BaseModel):
    """Schema for updating an existing document."""

    extracted_text: Optional[str] = None
    processing_status: Optional[str] = None
    processing_error: Optional[str] = None

    # AI metadata updates
    overarching_theme: Optional[str] = None
    recurring_topics: Optional[List[str]] = None
    pain_points: Optional[List[str]] = None
    analytical_insights: Optional[str] = None
    conclusion: Optional[str] = None
    keywords: Optional[List[str]] = None

    # Vector storage updates
    vector_stored: Optional[bool] = None
    vector_id: Optional[str] = None
    embedding_model: Optional[str] = None

    # Processing metrics
    token_count: Optional[int] = None
    processing_time_seconds: Optional[float] = None
    chunk_count: Optional[int] = None

    metadata_json: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None

    @validator("processing_status")
    def validate_processing_status(cls, v):
        """Validate processing status values."""
        if v is not None:
            valid_statuses = ["pending", "processing", "completed", "failed", "skipped"]
            if v not in valid_statuses:
                raise ValueError(f"processing_status must be one of: {valid_statuses}")
        return v


class DocumentResponse(DocumentBase):
    """Schema for document API responses."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentSummary(BaseModel):
    """Lightweight document summary for lists and search results."""

    id: int
    file_id: str
    original_filename: str
    file_type: str
    processing_status: str
    overarching_theme: Optional[str] = None
    keywords: Optional[List[str]] = None
    created_at: datetime
    vector_stored: bool = False

    class Config:
        from_attributes = True


class DocumentSearchQuery(BaseModel):
    """Schema for document search queries."""

    query: str = Field(..., min_length=1, description="Search query")
    file_types: Optional[List[str]] = Field(None, description="Filter by file types")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    processing_status: Optional[List[str]] = Field(None, description="Filter by processing status")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results to return")
    include_content: bool = Field(default=False, description="Include extracted text in results")

    @validator("file_types", "tags", "processing_status")
    def clean_filter_lists(cls, v):
        """Clean up filter lists."""
        if v:
            return [item.strip().lower() for item in v if item and item.strip()]
        return v


class DocumentStats(BaseModel):
    """Document statistics for dashboard/monitoring."""

    total_documents: int
    by_status: Dict[str, int]
    by_file_type: Dict[str, int]
    total_size_bytes: int
    processing_metrics: Dict[str, float]  # avg processing time, etc.
    vector_storage_stats: Dict[str, int]


# =============================================================================
# Utility Functions
# =============================================================================

def create_document_from_file_info(
    file_id: str,
    filename: str,
    file_size: int,
    mime_type: str = None,
    google_drive_id: str = None
) -> DocumentCreate:
    """
    Create a DocumentCreate instance from basic file information.

    Args:
        file_id: Unique file identifier
        filename: Original filename
        file_size: File size in bytes
        mime_type: File MIME type
        google_drive_id: Google Drive file ID if applicable

    Returns:
        DocumentCreate instance
    """
    # Extract file type from filename
    file_type = filename.split('.')[-1].lower() if '.' in filename else 'unknown'

    return DocumentCreate(
        file_id=file_id,
        original_filename=filename,
        file_type=file_type,
        file_size_bytes=file_size,
        mime_type=mime_type,
        google_drive_id=google_drive_id
    )


def get_file_type_from_mime(mime_type: str) -> str:
    """
    Get file type from MIME type.

    Args:
        mime_type: MIME type string

    Returns:
        File extension/type
    """
    mime_to_ext = {
        'application/pdf': 'pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
        'application/msword': 'doc',
        'text/plain': 'txt',
        'text/csv': 'csv',
        'application/vnd.ms-excel': 'xls',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/gif': 'gif',
        'image/webp': 'webp'
    }

    return mime_to_ext.get(mime_type, 'unknown')