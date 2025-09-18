"""
Database configuration and session management for Telegram Assistant.
Supports both SQLite (development) and PostgreSQL (production).
"""

import asyncio
from typing import AsyncGenerator, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Boolean, Text, Float
from contextlib import asynccontextmanager

from .config import settings
from .logger import get_logger
from .exceptions import DatabaseError, ConnectionError

logger = get_logger(__name__)


# =============================================================================
# DATABASE BASE CLASS
# =============================================================================

class Base(DeclarativeBase):
    """Base class for all database models."""

    # Common fields for all models
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


# =============================================================================
# DATABASE ENGINE SETUP
# =============================================================================

def get_database_url() -> str:
    """Get the appropriate database URL based on configuration."""
    db_url = settings.database_url

    # Convert synchronous URLs to async
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)

    return db_url


def create_database_engine():
    """Create database engine with appropriate configuration."""
    database_url = get_database_url()

    logger.info(f"Creating database engine for: {database_url.split('@')[-1] if '@' in database_url else database_url}")

    # Engine configuration
    engine_kwargs = {
        "echo": settings.is_development and settings.debug,
        "future": True,
    }

    # SQLite specific configuration
    if database_url.startswith("sqlite"):
        engine_kwargs.update({
            "pool_pre_ping": True,
            "connect_args": {"check_same_thread": False}
        })
    # PostgreSQL specific configuration
    else:
        engine_kwargs.update({
            "pool_size": 20,
            "max_overflow": 0,
            "pool_pre_ping": True,
            "pool_recycle": 3600,  # 1 hour
        })

    try:
        engine = create_async_engine(database_url, **engine_kwargs)
        return engine
    except Exception as e:
        logger.error(f"Failed to create database engine: {e}")
        raise ConnectionError(
            message=f"Failed to create database engine: {str(e)}",
            error_code="DB_ENGINE_CREATION_FAILED",
            details={"database_url": database_url.split('@')[-1] if '@' in database_url else database_url}
        )


# Global engine instance
engine = create_database_engine()

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# =============================================================================
# DATABASE SESSION MANAGEMENT
# =============================================================================

async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session.
    Use this as a dependency in FastAPI endpoints.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise DatabaseError(
                message=f"Database operation failed: {str(e)}",
                error_code="DB_SESSION_ERROR"
            )
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session():
    """
    Context manager for database sessions.
    Use this for manual database operations outside of FastAPI.
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Database session error: {e}")
        raise DatabaseError(
            message=f"Database operation failed: {str(e)}",
            error_code="DB_SESSION_ERROR"
        )
    finally:
        await session.close()


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

async def create_tables():
    """Create all database tables."""
    logger.info("Creating database tables...")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")

    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise DatabaseError(
            message=f"Failed to create database tables: {str(e)}",
            error_code="DB_TABLE_CREATION_FAILED"
        )


async def drop_tables():
    """Drop all database tables (use with caution!)."""
    logger.warning("Dropping all database tables...")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.warning("Database tables dropped")

    except Exception as e:
        logger.error(f"Failed to drop database tables: {e}")
        raise DatabaseError(
            message=f"Failed to drop database tables: {str(e)}",
            error_code="DB_TABLE_DROP_FAILED"
        )


async def check_database_connection() -> bool:
    """
    Check if database connection is working.

    Returns:
        bool: True if connection is working, False otherwise
    """
    try:
        async with engine.begin() as conn:
            await conn.execute("SELECT 1" if not settings.database_url.startswith("sqlite") else "SELECT 1")

        logger.info("Database connection check successful")
        return True

    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


async def get_database_info() -> dict:
    """
    Get information about the database.

    Returns:
        dict: Database information
    """
    try:
        async with get_db_session() as session:
            # Get basic connection info
            database_url = get_database_url()
            is_sqlite = database_url.startswith("sqlite")

            info = {
                "type": "sqlite" if is_sqlite else "postgresql",
                "url": database_url.split('@')[-1] if '@' in database_url else database_url,
                "connected": await check_database_connection(),
                "tables": []
            }

            # Get table information
            async with engine.begin() as conn:
                if is_sqlite:
                    result = await conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                else:
                    result = await conn.execute(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
                    )

                info["tables"] = [row[0] for row in result.fetchall()]

            return info

    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        return {
            "type": "unknown",
            "connected": False,
            "error": str(e)
        }


# =============================================================================
# DATABASE UTILITIES
# =============================================================================

async def cleanup_old_records(
    model_class,
    days_old: int = 30,
    batch_size: int = 1000
) -> int:
    """
    Clean up old records from a model.

    Args:
        model_class: SQLAlchemy model class
        days_old: Delete records older than this many days
        batch_size: Process records in batches of this size

    Returns:
        int: Number of records deleted
    """
    from sqlalchemy import select, delete
    from datetime import datetime, timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=days_old)
    deleted_count = 0

    try:
        async with get_db_session() as session:
            while True:
                # Find batch of old records
                result = await session.execute(
                    select(model_class.id)
                    .where(model_class.created_at < cutoff_date)
                    .limit(batch_size)
                )

                old_ids = [row[0] for row in result.fetchall()]

                if not old_ids:
                    break

                # Delete the batch
                delete_result = await session.execute(
                    delete(model_class).where(model_class.id.in_(old_ids))
                )

                batch_deleted = delete_result.rowcount
                deleted_count += batch_deleted

                await session.commit()

                logger.info(f"Deleted {batch_deleted} old records from {model_class.__name__}")

                if batch_deleted < batch_size:
                    break

        logger.info(f"Cleanup completed: {deleted_count} total records deleted from {model_class.__name__}")
        return deleted_count

    except Exception as e:
        logger.error(f"Failed to cleanup old records: {e}")
        raise DatabaseError(
            message=f"Failed to cleanup old records: {str(e)}",
            error_code="DB_CLEANUP_FAILED"
        )


async def get_table_stats() -> dict:
    """Get statistics about database tables."""
    stats = {}

    try:
        async with get_db_session() as session:
            # Import all model classes
            from ..models import (
                Document, ChatMessage, FileMetadata,
                UserProfile, ProcessingJob
            )

            models = [Document, ChatMessage, FileMetadata, UserProfile, ProcessingJob]

            for model in models:
                try:
                    from sqlalchemy import select, func

                    # Get count
                    count_result = await session.execute(
                        select(func.count(model.id))
                    )
                    count = count_result.scalar()

                    # Get oldest and newest records
                    oldest_result = await session.execute(
                        select(func.min(model.created_at))
                    )
                    oldest = oldest_result.scalar()

                    newest_result = await session.execute(
                        select(func.max(model.created_at))
                    )
                    newest = newest_result.scalar()

                    stats[model.__name__] = {
                        "count": count,
                        "oldest": oldest.isoformat() if oldest else None,
                        "newest": newest.isoformat() if newest else None
                    }

                except Exception as model_error:
                    stats[model.__name__] = {"error": str(model_error)}

        return stats

    except Exception as e:
        logger.error(f"Failed to get table stats: {e}")
        return {"error": str(e)}


# =============================================================================
# DATABASE HEALTH CHECK
# =============================================================================

async def health_check() -> dict:
    """
    Perform a comprehensive database health check.

    Returns:
        dict: Health check results
    """
    health = {
        "status": "unknown",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }

    try:
        # Connection check
        health["checks"]["connection"] = await check_database_connection()

        # Get database info
        db_info = await get_database_info()
        health["checks"]["database_info"] = db_info

        # Get table stats
        table_stats = await get_table_stats()
        health["checks"]["table_stats"] = table_stats

        # Determine overall status
        if health["checks"]["connection"] and db_info.get("connected"):
            health["status"] = "healthy"
        else:
            health["status"] = "unhealthy"

    except Exception as e:
        health["status"] = "error"
        health["error"] = str(e)
        logger.error(f"Database health check failed: {e}")

    return health


if __name__ == "__main__":
    # Test database connection
    async def test_database():
        print("Testing database connection...")

        # Check connection
        connected = await check_database_connection()
        print(f"Database connected: {connected}")

        if connected:
            # Get database info
            info = await get_database_info()
            print(f"Database info: {info}")

            # Health check
            health = await health_check()
            print(f"Health check: {health}")

    # Run test
    asyncio.run(test_database())