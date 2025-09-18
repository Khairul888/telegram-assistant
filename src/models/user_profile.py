"""
User profile model for storing information about Telegram users.
Supports user tracking and personalization features.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Text, JSON, Boolean
from pydantic import BaseModel, Field, validator

from ..core.database import Base


# =============================================================================
# SQLAlchemy ORM Model
# =============================================================================

class UserProfile(Base):
    """User profile model for storing Telegram user information and preferences."""

    __tablename__ = "user_profiles"

    # Telegram user identification
    telegram_user_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    telegram_chat_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)

    # User information
    username: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    language_code: Mapped[Optional[str]] = mapped_column(String(10))

    # Activity tracking
    first_interaction: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_interaction: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    total_queries: Mapped[int] = mapped_column(Integer, default=0)

    # User preferences
    preferred_language: Mapped[Optional[str]] = mapped_column(String(10))
    timezone: Mapped[Optional[str]] = mapped_column(String(50))
    notification_settings: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    # Usage statistics
    documents_processed: Mapped[int] = mapped_column(Integer, default=0)
    files_uploaded: Mapped[int] = mapped_column(Integer, default=0)
    ai_interactions: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0)

    # User status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    # Personalization data
    interests: Mapped[Optional[List[str]]] = mapped_column(JSON)  # User interests/topics
    search_history: Mapped[Optional[List[str]]] = mapped_column(JSON)  # Recent search queries
    document_categories: Mapped[Optional[List[str]]] = mapped_column(JSON)  # Document categories interacted with

    # Context and memory
    conversation_context: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    memory_preferences: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    # Additional metadata
    telegram_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)  # Raw Telegram user data
    custom_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    def __repr__(self):
        return f"<UserProfile(id={self.id}, telegram_user_id='{self.telegram_user_id}', username='{self.username}')>"

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) or self.username or f"User {self.telegram_user_id}"

    @property
    def display_name(self) -> str:
        """Get user's display name for UI."""
        if self.username:
            return f"@{self.username}"
        return self.full_name


# =============================================================================
# Pydantic Schemas
# =============================================================================

class UserProfileBase(BaseModel):
    """Base schema for UserProfile with common fields."""

    telegram_user_id: str = Field(..., description="Telegram user ID")
    telegram_chat_id: str = Field(..., description="Telegram chat ID")
    username: Optional[str] = Field(None, description="Telegram username")
    first_name: Optional[str] = Field(None, description="User's first name")
    last_name: Optional[str] = Field(None, description="User's last name")
    language_code: Optional[str] = Field(None, description="User's language code")

    first_interaction: datetime = Field(default_factory=datetime.utcnow, description="First interaction time")
    last_interaction: datetime = Field(default_factory=datetime.utcnow, description="Last interaction time")
    total_messages: int = Field(default=0, ge=0, description="Total messages sent")
    total_queries: int = Field(default=0, ge=0, description="Total queries made")

    preferred_language: Optional[str] = Field(None, description="Preferred language")
    timezone: Optional[str] = Field(None, description="User's timezone")
    notification_settings: Optional[Dict[str, Any]] = Field(None, description="Notification preferences")

    documents_processed: int = Field(default=0, ge=0, description="Documents processed count")
    files_uploaded: int = Field(default=0, ge=0, description="Files uploaded count")
    ai_interactions: int = Field(default=0, ge=0, description="AI interactions count")
    total_tokens_used: int = Field(default=0, ge=0, description="Total AI tokens used")

    is_active: bool = Field(default=True, description="Whether user is active")
    is_admin: bool = Field(default=False, description="Whether user is admin")
    is_blocked: bool = Field(default=False, description="Whether user is blocked")

    interests: Optional[List[str]] = Field(None, description="User interests/topics")
    search_history: Optional[List[str]] = Field(None, description="Recent search queries")
    document_categories: Optional[List[str]] = Field(None, description="Document categories")

    conversation_context: Optional[Dict[str, Any]] = Field(None, description="Conversation context")
    memory_preferences: Optional[Dict[str, Any]] = Field(None, description="Memory preferences")

    telegram_data: Optional[Dict[str, Any]] = Field(None, description="Raw Telegram data")
    custom_metadata: Optional[Dict[str, Any]] = Field(None, description="Custom metadata")

    @validator("telegram_user_id", "telegram_chat_id")
    def validate_ids(cls, v):
        """Clean up ID fields."""
        if v:
            return str(v).strip()
        return v

    @validator("username")
    def validate_username(cls, v):
        """Clean up username."""
        if v:
            username = v.strip()
            # Remove @ if present
            if username.startswith('@'):
                username = username[1:]
            return username
        return v

    @validator("interests", "search_history", "document_categories")
    def validate_string_lists(cls, v):
        """Clean up string lists."""
        if v:
            return [item.strip() for item in v if item and item.strip()]
        return v

    @validator("search_history")
    def limit_search_history(cls, v):
        """Limit search history to last 50 items."""
        if v and len(v) > 50:
            return v[-50:]
        return v


class UserProfileCreate(UserProfileBase):
    """Schema for creating a new user profile."""
    pass


class UserProfileUpdate(BaseModel):
    """Schema for updating user profile."""

    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None

    last_interaction: Optional[datetime] = None
    total_messages: Optional[int] = None
    total_queries: Optional[int] = None

    preferred_language: Optional[str] = None
    timezone: Optional[str] = None
    notification_settings: Optional[Dict[str, Any]] = None

    documents_processed: Optional[int] = None
    files_uploaded: Optional[int] = None
    ai_interactions: Optional[int] = None
    total_tokens_used: Optional[int] = None

    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    is_blocked: Optional[bool] = None

    interests: Optional[List[str]] = None
    search_history: Optional[List[str]] = None
    document_categories: Optional[List[str]] = None

    conversation_context: Optional[Dict[str, Any]] = None
    memory_preferences: Optional[Dict[str, Any]] = None

    telegram_data: Optional[Dict[str, Any]] = None
    custom_metadata: Optional[Dict[str, Any]] = None

    @validator("username")
    def validate_username(cls, v):
        """Clean up username."""
        if v:
            username = v.strip()
            if username.startswith('@'):
                username = username[1:]
            return username
        return v


class UserProfileResponse(UserProfileBase):
    """Schema for user profile API responses."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserProfileSummary(BaseModel):
    """Lightweight user profile summary."""

    id: int
    telegram_user_id: str
    username: Optional[str] = None
    full_name: str
    last_interaction: datetime
    total_messages: int
    is_active: bool

    class Config:
        from_attributes = True


class UserStats(BaseModel):
    """User statistics for monitoring."""

    total_users: int
    active_users: int
    new_users_today: int
    new_users_this_week: int
    top_users_by_messages: List[Dict[str, Any]]
    usage_metrics: Dict[str, Any]


class ActivityUpdate(BaseModel):
    """Schema for updating user activity."""

    message_sent: bool = False
    query_made: bool = False
    document_processed: bool = False
    file_uploaded: bool = False
    ai_interaction: bool = False
    tokens_used: int = 0


# =============================================================================
# Utility Functions
# =============================================================================

def create_user_profile_from_telegram(
    telegram_user: Dict[str, Any],
    chat_id: str
) -> UserProfileCreate:
    """
    Create UserProfile from Telegram user data.

    Args:
        telegram_user: Telegram user object
        chat_id: Telegram chat ID

    Returns:
        UserProfileCreate instance
    """
    return UserProfileCreate(
        telegram_user_id=str(telegram_user["id"]),
        telegram_chat_id=str(chat_id),
        username=telegram_user.get("username"),
        first_name=telegram_user.get("first_name"),
        last_name=telegram_user.get("last_name"),
        language_code=telegram_user.get("language_code"),
        telegram_data=telegram_user
    )


def update_user_activity(
    user_id: str,
    activity: ActivityUpdate
) -> UserProfileUpdate:
    """
    Create an activity update for a user.

    Args:
        user_id: Telegram user ID
        activity: Activity update information

    Returns:
        UserProfileUpdate instance
    """
    update_data = {
        "last_interaction": datetime.utcnow()
    }

    if activity.message_sent:
        # Will be incremented in the service layer
        pass

    if activity.query_made:
        # Will be incremented in the service layer
        pass

    if activity.document_processed:
        # Will be incremented in the service layer
        pass

    if activity.file_uploaded:
        # Will be incremented in the service layer
        pass

    if activity.ai_interaction:
        # Will be incremented in the service layer
        pass

    if activity.tokens_used > 0:
        # Will be incremented in the service layer
        pass

    return UserProfileUpdate(**update_data)


def add_to_search_history(
    current_history: Optional[List[str]],
    new_query: str,
    max_history: int = 50
) -> List[str]:
    """
    Add a query to search history, maintaining size limit.

    Args:
        current_history: Current search history
        new_query: New search query to add
        max_history: Maximum history size

    Returns:
        Updated search history
    """
    history = current_history or []

    # Remove query if it already exists (to move it to the front)
    query = new_query.strip()
    if query in history:
        history.remove(query)

    # Add to front
    history.insert(0, query)

    # Limit size
    return history[:max_history]


def update_user_interests(
    current_interests: Optional[List[str]],
    new_topics: List[str],
    max_interests: int = 20
) -> List[str]:
    """
    Update user interests based on document topics.

    Args:
        current_interests: Current user interests
        new_topics: New topics from processed documents
        max_interests: Maximum interests to keep

    Returns:
        Updated interests list
    """
    interests = current_interests or []

    for topic in new_topics:
        topic = topic.strip()
        if topic and topic not in interests:
            interests.append(topic)

    # Keep most recent interests
    return interests[-max_interests:] if len(interests) > max_interests else interests


def get_default_notification_settings() -> Dict[str, Any]:
    """Get default notification settings for new users."""
    return {
        "processing_complete": True,
        "processing_failed": True,
        "new_documents": False,
        "daily_summary": False,
        "system_updates": True
    }


def get_default_memory_preferences() -> Dict[str, Any]:
    """Get default memory preferences for new users."""
    return {
        "remember_preferences": True,
        "context_window_size": 40,
        "save_search_history": True,
        "personalize_responses": True
    }