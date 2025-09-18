"""
Data models for Telegram Assistant.
All database models and schemas are defined here.
"""

from .document import Document, DocumentCreate, DocumentUpdate, DocumentResponse
from .chat_message import ChatMessage, ChatMessageCreate, ChatMessageResponse
from .file_metadata import FileMetadata, FileMetadataCreate, FileMetadataUpdate
from .user_profile import UserProfile, UserProfileCreate, UserProfileUpdate
from .processing_job import ProcessingJob, ProcessingJobCreate, ProcessingJobUpdate, JobStatus

__all__ = [
    "Document",
    "DocumentCreate",
    "DocumentUpdate",
    "DocumentResponse",
    "ChatMessage",
    "ChatMessageCreate",
    "ChatMessageResponse",
    "FileMetadata",
    "FileMetadataCreate",
    "FileMetadataUpdate",
    "UserProfile",
    "UserProfileCreate",
    "UserProfileUpdate",
    "ProcessingJob",
    "ProcessingJobCreate",
    "ProcessingJobUpdate",
    "JobStatus"
]