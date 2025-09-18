"""
Simple tests to validate core functionality without complex configuration dependencies.
"""

import pytest
import tempfile
import os
from pathlib import Path


def test_basic_python_functionality():
    """Test that basic Python functionality works."""
    assert 1 + 1 == 2
    assert "hello".upper() == "HELLO"


def test_file_operations():
    """Test basic file operations."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("test content")
        temp_path = f.name

    # Test file exists
    assert Path(temp_path).exists()

    # Test reading
    with open(temp_path, 'r') as f:
        content = f.read()
    assert content == "test content"

    # Cleanup
    os.unlink(temp_path)


def test_json_operations():
    """Test JSON operations."""
    import json

    data = {"key": "value", "number": 123}
    json_str = json.dumps(data)
    parsed = json.loads(json_str)

    assert parsed["key"] == "value"
    assert parsed["number"] == 123


def test_datetime_operations():
    """Test datetime operations."""
    from datetime import datetime

    now = datetime.now()
    assert isinstance(now, datetime)
    assert now.year >= 2024


def test_async_functionality():
    """Test basic async functionality."""
    import asyncio

    async def async_function():
        await asyncio.sleep(0.01)
        return "async result"

    result = asyncio.run(async_function())
    assert result == "async result"


def test_pydantic_basic():
    """Test basic Pydantic functionality."""
    from pydantic import BaseModel, Field

    class TestModel(BaseModel):
        name: str
        age: int = Field(gt=0)

    model = TestModel(name="test", age=25)
    assert model.name == "test"
    assert model.age == 25

    # Test validation
    with pytest.raises(Exception):
        TestModel(name="test", age=-1)


def test_fastapi_basic():
    """Test basic FastAPI functionality."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.get("/test")
    def test_endpoint():
        return {"message": "test"}

    client = TestClient(app)
    response = client.get("/test")

    assert response.status_code == 200
    assert response.json()["message"] == "test"


def test_sqlalchemy_basic():
    """Test basic SQLAlchemy functionality."""
    from sqlalchemy import create_engine, Column, Integer, String
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker

    Base = declarative_base()

    class TestTable(Base):
        __tablename__ = 'test_table'
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

    # Create in-memory SQLite database
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    # Test insert
    test_record = TestTable(name="test")
    session.add(test_record)
    session.commit()

    # Test query
    result = session.query(TestTable).first()
    assert result.name == "test"

    session.close()


def test_utilities_import():
    """Test that utility modules can be imported."""
    # These should import without errors
    try:
        import src.utils.file_utils
        import src.utils.text_utils
        import src.utils.validation_utils
        success = True
    except ImportError:
        success = False

    assert success, "Utility modules should be importable"


def test_models_import():
    """Test that model modules can be imported."""
    try:
        from src.models import (
            DocumentCreate, ChatMessageCreate, FileMetadataCreate,
            UserProfileCreate, ProcessingJobCreate
        )
        success = True
    except ImportError:
        success = False

    assert success, "Model classes should be importable"


def test_project_structure():
    """Test that project structure is correct."""
    project_root = Path(__file__).parent.parent

    # Check key directories exist
    assert (project_root / "src").exists()
    assert (project_root / "src" / "core").exists()
    assert (project_root / "src" / "models").exists()
    assert (project_root / "src" / "utils").exists()
    assert (project_root / "tests").exists()

    # Check key files exist
    assert (project_root / "main.py").exists()
    assert (project_root / "requirements.txt").exists()
    assert (project_root / ".env.example").exists()


@pytest.mark.asyncio
async def test_async_database_basic():
    """Test basic async database functionality."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    # Create async in-memory database
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async_session = sessionmaker(engine, class_=AsyncSession)

    async with async_session() as session:
        # Just test that session creation works
        assert session is not None

    await engine.dispose()


def test_environment_variables():
    """Test environment variable handling."""
    import os

    # Test setting and getting env vars
    test_var = "TEST_VARIABLE"
    test_value = "test_value"

    os.environ[test_var] = test_value
    assert os.getenv(test_var) == test_value

    # Clean up
    del os.environ[test_var]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])