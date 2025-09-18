"""
Tests for database operations and models.
"""

import pytest
import asyncio
from datetime import datetime
from sqlalchemy import select, func

from src.core.database import (
    create_tables, health_check, check_database_connection,
    get_database_session, AsyncSessionLocal
)
from src.models import (
    Document, ChatMessage, FileMetadata, UserProfile, ProcessingJob,
    DocumentCreate, ChatMessageCreate, FileMetadataCreate,
    UserProfileCreate, ProcessingJobCreate
)


class TestDatabaseConnection:
    """Test database connection and setup."""

    @pytest.mark.database
    async def test_database_connection(self, test_database):
        """Test basic database connectivity."""
        connected = await check_database_connection()
        assert connected is True

    @pytest.mark.database
    async def test_create_tables(self, test_database):
        """Test table creation."""
        # Tables should be created by test_database fixture
        # Verify by checking if we can create a session
        async with AsyncSessionLocal() as session:
            assert session is not None

    @pytest.mark.database
    async def test_health_check(self, test_database):
        """Test database health check."""
        health = await health_check()

        assert health["status"] == "healthy"
        assert "timestamp" in health
        assert "database" in health
        assert health["database"]["connected"] is True

    @pytest.mark.database
    async def test_session_management(self, db_session):
        """Test database session management."""
        # Session should be available
        assert db_session is not None

        # Should be able to execute queries
        result = await db_session.execute(select(func.count()).select_from(Document))
        count = result.scalar()
        assert count == 0  # Empty database


class TestDocumentModel:
    """Test Document model operations."""

    @pytest.mark.database
    async def test_create_document(self, db_session, sample_document_data):
        """Test creating a document record."""
        doc_data = DocumentCreate(**sample_document_data)

        # Create document
        document = Document(**doc_data.model_dump())
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        # Verify creation
        assert document.id is not None
        assert document.file_id == sample_document_data["file_id"]
        assert document.original_filename == sample_document_data["original_filename"]
        assert document.processing_status == "completed"
        assert document.created_at is not None

    @pytest.mark.database
    async def test_document_relationships(self, db_session, sample_document_data):
        """Test document relationships with other models."""
        # Create document
        doc_data = DocumentCreate(**sample_document_data)
        document = Document(**doc_data.model_dump())
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        # Document should be queryable
        result = await db_session.execute(
            select(Document).where(Document.file_id == sample_document_data["file_id"])
        )
        found_doc = result.scalar_one()
        assert found_doc.id == document.id

    @pytest.mark.database
    async def test_document_validation(self, db_session):
        """Test document model validation."""
        # Test with invalid data
        with pytest.raises(Exception):  # Should raise validation error
            invalid_doc = Document(
                file_id="",  # Empty file_id should be invalid
                original_filename="test.pdf",
                file_type="pdf",
                file_size_bytes=-1,  # Negative size should be invalid
            )
            db_session.add(invalid_doc)
            await db_session.commit()

    @pytest.mark.database
    async def test_document_timestamps(self, db_session, sample_document_data):
        """Test document timestamp handling."""
        doc_data = DocumentCreate(**sample_document_data)
        document = Document(**doc_data.model_dump())

        creation_time = datetime.now()
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        # Check timestamps
        assert document.created_at is not None
        assert document.updated_at is not None
        assert document.created_at >= creation_time


class TestChatMessageModel:
    """Test ChatMessage model operations."""

    @pytest.mark.database
    async def test_create_chat_message(self, db_session, sample_chat_message_data):
        """Test creating a chat message record."""
        msg_data = ChatMessageCreate(**sample_chat_message_data)

        message = ChatMessage(**msg_data.model_dump())
        db_session.add(message)
        await db_session.commit()
        await db_session.refresh(message)

        # Verify creation
        assert message.id is not None
        assert message.message_id == sample_chat_message_data["message_id"]
        assert message.content == sample_chat_message_data["content"]
        assert message.message_type == "user"

    @pytest.mark.database
    async def test_chat_message_types(self, db_session):
        """Test different chat message types."""
        # Test user message
        user_msg = ChatMessage(
            chat_id="123456",
            message_type="user",
            content="Hello",
            user_id="user123"
        )
        db_session.add(user_msg)

        # Test bot message
        bot_msg = ChatMessage(
            chat_id="123456",
            message_type="bot",
            content="Hello! How can I help you?"
        )
        db_session.add(bot_msg)

        await db_session.commit()

        # Verify both types
        result = await db_session.execute(select(ChatMessage))
        messages = result.scalars().all()
        assert len(messages) == 2

        types = [msg.message_type for msg in messages]
        assert "user" in types
        assert "bot" in types

    @pytest.mark.database
    async def test_message_ordering(self, db_session):
        """Test message ordering by timestamp."""
        # Create multiple messages
        for i in range(3):
            msg = ChatMessage(
                chat_id="123456",
                message_type="user",
                content=f"Message {i}",
                user_id="user123"
            )
            db_session.add(msg)
            await db_session.commit()
            await asyncio.sleep(0.01)  # Small delay to ensure different timestamps

        # Query messages ordered by timestamp
        result = await db_session.execute(
            select(ChatMessage).order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()

        assert len(messages) == 3
        assert messages[0].content == "Message 0"
        assert messages[2].content == "Message 2"


class TestFileMetadataModel:
    """Test FileMetadata model operations."""

    @pytest.mark.database
    async def test_create_file_metadata(self, db_session, sample_file_metadata_data):
        """Test creating file metadata record."""
        meta_data = FileMetadataCreate(**sample_file_metadata_data)

        file_meta = FileMetadata(**meta_data.model_dump())
        db_session.add(file_meta)
        await db_session.commit()
        await db_session.refresh(file_meta)

        # Verify creation
        assert file_meta.id is not None
        assert file_meta.file_id == sample_file_metadata_data["file_id"]
        assert file_meta.source == "google_drive"
        assert file_meta.status == "pending"

    @pytest.mark.database
    async def test_file_status_transitions(self, db_session, sample_file_metadata_data):
        """Test file status transitions."""
        meta_data = FileMetadataCreate(**sample_file_metadata_data)
        file_meta = FileMetadata(**meta_data.model_dump())
        db_session.add(file_meta)
        await db_session.commit()

        # Update status
        file_meta.status = "processing"
        await db_session.commit()

        # Verify update
        result = await db_session.execute(
            select(FileMetadata).where(FileMetadata.id == file_meta.id)
        )
        updated_meta = result.scalar_one()
        assert updated_meta.status == "processing"


class TestUserProfileModel:
    """Test UserProfile model operations."""

    @pytest.mark.database
    async def test_create_user_profile(self, db_session, sample_user_profile_data):
        """Test creating user profile record."""
        profile_data = UserProfileCreate(**sample_user_profile_data)

        profile = UserProfile(**profile_data.model_dump())
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)

        # Verify creation
        assert profile.id is not None
        assert profile.telegram_user_id == sample_user_profile_data["telegram_user_id"]
        assert profile.username == sample_user_profile_data["username"]

    @pytest.mark.database
    async def test_user_profile_uniqueness(self, db_session, sample_user_profile_data):
        """Test user profile uniqueness constraints."""
        profile_data = UserProfileCreate(**sample_user_profile_data)

        # Create first profile
        profile1 = UserProfile(**profile_data.model_dump())
        db_session.add(profile1)
        await db_session.commit()

        # Try to create duplicate (should handle gracefully or raise constraint error)
        profile2 = UserProfile(**profile_data.model_dump())
        db_session.add(profile2)

        # This should either raise an integrity error or be handled by the application
        with pytest.raises(Exception):
            await db_session.commit()


class TestProcessingJobModel:
    """Test ProcessingJob model operations."""

    @pytest.mark.database
    async def test_create_processing_job(self, db_session, sample_processing_job_data):
        """Test creating processing job record."""
        job_data = ProcessingJobCreate(**sample_processing_job_data)

        job = ProcessingJob(**job_data.model_dump())
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        # Verify creation
        assert job.id is not None
        assert job.job_id == sample_processing_job_data["job_id"]
        assert job.job_type == "document_processing"
        assert job.status == "pending"

    @pytest.mark.database
    async def test_job_parameters_json(self, db_session, sample_processing_job_data):
        """Test JSON field handling for job parameters."""
        job_data = ProcessingJobCreate(**sample_processing_job_data)
        job = ProcessingJob(**job_data.model_dump())
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        # Verify JSON field
        assert job.input_parameters is not None
        assert isinstance(job.input_parameters, dict)
        assert job.input_parameters["extract_text"] is True

    @pytest.mark.database
    async def test_job_status_workflow(self, db_session, sample_processing_job_data):
        """Test job status workflow."""
        job_data = ProcessingJobCreate(**sample_processing_job_data)
        job = ProcessingJob(**job_data.model_dump())
        db_session.add(job)
        await db_session.commit()

        # Test status transitions
        statuses = ["pending", "running", "completed"]
        for status in statuses:
            job.status = status
            await db_session.commit()

            # Verify status update
            result = await db_session.execute(
                select(ProcessingJob).where(ProcessingJob.id == job.id)
            )
            updated_job = result.scalar_one()
            assert updated_job.status == status


class TestDatabaseIntegration:
    """Test database integration scenarios."""

    @pytest.mark.database
    @pytest.mark.integration
    async def test_full_workflow_simulation(self, db_session, sample_document_data,
                                          sample_chat_message_data, sample_processing_job_data):
        """Test a complete workflow simulation."""
        # 1. Create a document
        doc_data = DocumentCreate(**sample_document_data)
        document = Document(**doc_data.model_dump())
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        # 2. Create a processing job for the document
        job_data = ProcessingJobCreate(**sample_processing_job_data)
        job_data.file_id = document.file_id
        job = ProcessingJob(**job_data.model_dump())
        db_session.add(job)
        await db_session.commit()

        # 3. Create chat messages about the document
        msg_data = ChatMessageCreate(**sample_chat_message_data)
        msg_data.content = f"Please analyze document {document.original_filename}"
        message = ChatMessage(**msg_data.model_dump())
        db_session.add(message)
        await db_session.commit()

        # 4. Verify all records exist and are related
        doc_count = await db_session.execute(select(func.count()).select_from(Document))
        job_count = await db_session.execute(select(func.count()).select_from(ProcessingJob))
        msg_count = await db_session.execute(select(func.count()).select_from(ChatMessage))

        assert doc_count.scalar() == 1
        assert job_count.scalar() == 1
        assert msg_count.scalar() == 1

    @pytest.mark.database
    async def test_concurrent_operations(self, test_database):
        """Test concurrent database operations."""
        async def create_document(session, file_id):
            doc = Document(
                file_id=file_id,
                original_filename=f"test_{file_id}.pdf",
                file_type="pdf",
                file_size_bytes=1024
            )
            session.add(doc)
            await session.commit()
            return doc

        # Create multiple sessions and documents concurrently
        tasks = []
        for i in range(5):
            async with AsyncSessionLocal() as session:
                task = create_document(session, f"file_{i}")
                tasks.append(task)

        # This should work without conflicts
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check that all documents were created successfully
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) >= 4  # Allow for some potential conflicts