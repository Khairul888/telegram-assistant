"""
Chat message model for storing conversation history.
Supports the conversational AI interface from the n8n workflow.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Text, JSON, Boolean, ForeignKey
from pydantic import BaseModel, Field, validator

from ..core.database import Base


# =============================================================================
# SQLAlchemy ORM Model
# =============================================================================

class ChatMessage(Base):
    """Chat message model for storing conversation history."""

    __tablename__ = "chat_messages"

    # Message identification
    message_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)  # Telegram message ID
    chat_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)  # Telegram chat ID

    # Message content
    message_type: Mapped[str] = mapped_column(String(50), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # User information
    user_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    username: Mapped[Optional[str]] = mapped_column(String(100))
    user_first_name: Mapped[Optional[str]] = mapped_column(String(100))
    user_last_name: Mapped[Optional[str]] = mapped_column(String(100))

    # Message context
    reply_to_message_id: Mapped[Optional[str]] = mapped_column(String(100))
    thread_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)  # For grouping conversations

    # AI processing information
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_response_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_time_seconds: Mapped[Optional[float]] = mapped_column()

    # Context and memory
    context_documents: Mapped[Optional[List[str]]] = mapped_column(JSON)  # Document IDs used as context
    memory_window_position: Mapped[Optional[int]] = mapped_column(Integer)  # Position in memory window

    # AI metadata
    intent: Mapped[Optional[str]] = mapped_column(String(100))  # Detected user intent
    confidence_score: Mapped[Optional[float]] = mapped_column()  # AI confidence in response
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)  # Tokens consumed

    # Additional metadata
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    # Telegram-specific fields
    telegram_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)  # Raw Telegram message data

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, type='{self.message_type}', chat_id='{self.chat_id}')>"


# =============================================================================
# Pydantic Schemas
# =============================================================================

class ChatMessageBase(BaseModel):
    """Base schema for ChatMessage with common fields."""

    message_id: Optional[str] = Field(None, description="Telegram message ID")
    chat_id: str = Field(..., description="Telegram chat ID")
    message_type: str = Field(..., description="Type of message (user, assistant, system)")
    content: str = Field(..., description="Message content")

    user_id: Optional[str] = Field(None, description="Telegram user ID")
    username: Optional[str] = Field(None, description="Telegram username")
    user_first_name: Optional[str] = Field(None, description="User's first name")
    user_last_name: Optional[str] = Field(None, description="User's last name")

    reply_to_message_id: Optional[str] = Field(None, description="ID of message being replied to")
    thread_id: Optional[str] = Field(None, description="Conversation thread ID")

    processed: bool = Field(default=False, description="Whether message has been processed")
    ai_response_generated: bool = Field(default=False, description="Whether AI response was generated")
    processing_time_seconds: Optional[float] = Field(None, ge=0, description="Processing time")

    context_documents: Optional[List[str]] = Field(None, description="Document IDs used as context")
    memory_window_position: Optional[int] = Field(None, ge=0, description="Position in memory window")

    intent: Optional[str] = Field(None, description="Detected user intent")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="AI confidence score")
    tokens_used: Optional[int] = Field(None, ge=0, description="Tokens consumed")

    metadata_json: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    telegram_data: Optional[Dict[str, Any]] = Field(None, description="Raw Telegram data")

    @validator("message_type")
    def validate_message_type(cls, v):
        """Validate message type."""
        valid_types = ["user", "assistant", "system", "error", "notification"]
        if v not in valid_types:
            raise ValueError(f"message_type must be one of: {valid_types}")
        return v

    @validator("content")
    def validate_content(cls, v):
        """Ensure content is not empty."""
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty")
        return v.strip()

    @validator("chat_id", "user_id")
    def validate_ids(cls, v):
        """Clean up ID fields."""
        if v:
            return str(v).strip()
        return v


class ChatMessageCreate(ChatMessageBase):
    """Schema for creating a new chat message."""
    pass


class ChatMessageResponse(ChatMessageBase):
    """Schema for chat message API responses."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatMessageUpdate(BaseModel):
    """Schema for updating chat message."""

    processed: Optional[bool] = None
    ai_response_generated: Optional[bool] = None
    processing_time_seconds: Optional[float] = None
    context_documents: Optional[List[str]] = None
    memory_window_position: Optional[int] = None
    intent: Optional[str] = None
    confidence_score: Optional[float] = None
    tokens_used: Optional[int] = None
    metadata_json: Optional[Dict[str, Any]] = None

    @validator("confidence_score")
    def validate_confidence(cls, v):
        """Validate confidence score range."""
        if v is not None and not (0 <= v <= 1):
            raise ValueError("confidence_score must be between 0 and 1")
        return v


class ConversationContext(BaseModel):
    """Schema for conversation context information."""

    chat_id: str
    recent_messages: List[ChatMessageResponse]
    total_messages: int
    context_documents: List[str]
    current_thread_id: Optional[str] = None
    memory_window_size: int = 40

    class Config:
        from_attributes = True


class ChatStats(BaseModel):
    """Chat statistics for monitoring."""

    total_messages: int
    by_type: Dict[str, int]
    by_chat: Dict[str, int]
    processing_metrics: Dict[str, float]
    ai_metrics: Dict[str, Any]


class MessageSearchQuery(BaseModel):
    """Schema for searching chat messages."""

    query: Optional[str] = Field(None, description="Search query for message content")
    chat_id: Optional[str] = Field(None, description="Filter by specific chat")
    message_type: Optional[str] = Field(None, description="Filter by message type")
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    thread_id: Optional[str] = Field(None, description="Filter by thread ID")
    date_from: Optional[datetime] = Field(None, description="Filter messages from this date")
    date_to: Optional[datetime] = Field(None, description="Filter messages until this date")
    limit: int = Field(default=50, ge=1, le=500, description="Maximum results")
    include_context: bool = Field(default=True, description="Include context information")

    @validator("message_type")
    def validate_message_type(cls, v):
        """Validate message type filter."""
        if v:
            valid_types = ["user", "assistant", "system", "error", "notification"]
            if v not in valid_types:
                raise ValueError(f"message_type must be one of: {valid_types}")
        return v


# =============================================================================
# Utility Functions
# =============================================================================

def create_user_message(
    chat_id: str,
    content: str,
    user_id: str = None,
    username: str = None,
    message_id: str = None,
    telegram_data: Dict[str, Any] = None
) -> ChatMessageCreate:
    """
    Create a user message from Telegram data.

    Args:
        chat_id: Telegram chat ID
        content: Message content
        user_id: Telegram user ID
        username: Telegram username
        message_id: Telegram message ID
        telegram_data: Raw Telegram message data

    Returns:
        ChatMessageCreate instance
    """
    return ChatMessageCreate(
        message_id=message_id,
        chat_id=str(chat_id),
        message_type="user",
        content=content,
        user_id=str(user_id) if user_id else None,
        username=username,
        telegram_data=telegram_data
    )


def create_assistant_message(
    chat_id: str,
    content: str,
    reply_to_message_id: str = None,
    context_documents: List[str] = None,
    processing_time: float = None,
    tokens_used: int = None,
    confidence_score: float = None
) -> ChatMessageCreate:
    """
    Create an assistant response message.

    Args:
        chat_id: Telegram chat ID
        content: Response content
        reply_to_message_id: ID of message being replied to
        context_documents: Document IDs used for context
        processing_time: Time taken to generate response
        tokens_used: Tokens consumed
        confidence_score: AI confidence in response

    Returns:
        ChatMessageCreate instance
    """
    return ChatMessageCreate(
        chat_id=str(chat_id),
        message_type="assistant",
        content=content,
        reply_to_message_id=reply_to_message_id,
        context_documents=context_documents,
        processing_time_seconds=processing_time,
        tokens_used=tokens_used,
        confidence_score=confidence_score,
        ai_response_generated=True,
        processed=True
    )


def create_system_message(
    chat_id: str,
    content: str,
    message_type: str = "system",
    metadata: Dict[str, Any] = None
) -> ChatMessageCreate:
    """
    Create a system message (notifications, errors, etc.).

    Args:
        chat_id: Telegram chat ID
        content: System message content
        message_type: Type of system message
        metadata: Additional metadata

    Returns:
        ChatMessageCreate instance
    """
    return ChatMessageCreate(
        chat_id=str(chat_id),
        message_type=message_type,
        content=content,
        metadata_json=metadata,
        processed=True
    )


def extract_telegram_user_info(telegram_user: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract user information from Telegram user object.

    Args:
        telegram_user: Telegram user data

    Returns:
        Dictionary with user information
    """
    return {
        "user_id": str(telegram_user.get("id", "")),
        "username": telegram_user.get("username", ""),
        "user_first_name": telegram_user.get("first_name", ""),
        "user_last_name": telegram_user.get("last_name", "")
    }