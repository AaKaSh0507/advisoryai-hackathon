"""
Pytest configuration and shared fixtures for all tests.

This module provides:
- Database session fixtures with transaction rollback
- Test client for FastAPI
- Mock services (storage, redis)
- Sample data factories
"""

import asyncio
import os
import sys
from collections.abc import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Add the workspace root to the Python path for absolute imports
workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, workspace_root)

# Set test environment variables BEFORE importing app modules
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "test_access_key")
os.environ.setdefault("S3_SECRET_KEY", "test_secret_key")
os.environ.setdefault("S3_BUCKET_NAME", "test-bucket")
os.environ.setdefault("LOG_DIR", "/tmp/test_logs")

# Monkey-patch JSONB to use JSON for SQLite compatibility
# This must be done before importing any models
from sqlalchemy.dialects import postgresql  # noqa: E402

postgresql.JSONB = JSON

from backend.app.config import Settings  # noqa: E402
from backend.app.domains.document.models import Document  # noqa: E402
from backend.app.domains.generation.models import (  # noqa: E402, F401
    GenerationInput,
    GenerationInputBatch,
)
from backend.app.domains.generation.section_output_models import (  # noqa: E402, F401
    SectionOutput,
    SectionOutputBatch,
)
from backend.app.infrastructure.database import Base  # noqa: E402

# ============================================================================
# Event Loop Configuration
# ============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Test Settings
# ============================================================================


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with in-memory database."""
    return Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/15",
        s3_endpoint_url="http://localhost:9000",
        s3_access_key="test_access_key",
        s3_secret_key="test_secret_key",
        s3_bucket_name="test-bucket",
        log_dir="/tmp/test_logs",
    )


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def async_engine():
    """Create async SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session with automatic rollback after each test."""
    async_session_maker = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


# ============================================================================
# Mock Storage Fixture
# ============================================================================


class MockStorageService:
    """In-memory mock for S3 storage service."""

    def __init__(self):
        self._files: dict[str, bytes] = {}

    def upload_template_source(self, template_id, version, file_obj) -> str:
        key = f"templates/{template_id}/{version}/source.docx"
        if hasattr(file_obj, "read"):
            content = file_obj.read()
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)
        else:
            content = file_obj
        self._files[key] = content
        return key

    def upload_template_parsed(self, template_id, version, file_obj) -> str:
        key = f"templates/{template_id}/{version}/parsed.json"
        if hasattr(file_obj, "read"):
            content = file_obj.read()
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)
        else:
            content = file_obj
        self._files[key] = content
        return key

    def upload_template_parsed_json(self, template_id, version, parsed_data) -> str:
        import json

        key = f"templates/{template_id}/{version}/parsed.json"
        self._files[key] = json.dumps(parsed_data).encode()
        return key

    def upload_document_output(self, document_id, version, file_obj) -> str:
        key = f"documents/{document_id}/{version}/output.docx"
        if hasattr(file_obj, "read"):
            content = file_obj.read()
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)
        else:
            content = file_obj
        self._files[key] = content
        return key

    def get_file(self, key: str) -> bytes | None:
        return self._files.get(key)

    def get_template_source(self, template_id, version) -> bytes | None:
        key = f"templates/{template_id}/{version}/source.docx"
        return self._files.get(key)

    def get_template_parsed(self, template_id, version) -> dict | None:
        import json

        key = f"templates/{template_id}/{version}/parsed.json"
        data = self._files.get(key)
        if data:
            return json.loads(data.decode())
        return None

    def file_exists(self, key: str) -> bool:
        return key in self._files

    def template_source_exists(self, template_id, version) -> bool:
        key = f"templates/{template_id}/{version}/source.docx"
        return key in self._files

    def template_parsed_exists(self, template_id, version) -> bool:
        key = f"templates/{template_id}/{version}/parsed.json"
        return key in self._files

    def delete_file(self, key: str) -> bool:
        if key in self._files:
            del self._files[key]
            return True
        return False

    def clear(self):
        """Clear all stored files."""
        self._files.clear()


@pytest.fixture
def mock_storage() -> MockStorageService:
    """Provide a mock storage service."""
    return MockStorageService()


# ============================================================================
# Mock Redis Fixture
# ============================================================================


class MockRedisClient:
    """In-memory mock for Redis client."""

    def __init__(self):
        self._data: dict[str, str] = {}
        self._sets: dict[str, set] = {}
        self._notifications: list[tuple] = []
        self._workers: dict[str, float] = {}
        self._locks: dict[str, str] = {}

    def notify_job_created(self, job_id, job_type: str):
        self._notifications.append((str(job_id), job_type))

    def register_worker(self, worker_id: str, ttl_seconds: int = 60):
        import time

        self._workers[worker_id] = time.time() + ttl_seconds

    def heartbeat(self, worker_id: str, ttl_seconds: int = 60):
        import time

        self._workers[worker_id] = time.time() + ttl_seconds

    def get_active_workers(self) -> list[str]:
        import time

        now = time.time()
        return [w for w, exp in self._workers.items() if exp > now]

    def acquire_lock(self, lock_name: str, ttl_seconds: int = 60) -> str | None:
        if lock_name in self._locks:
            return None
        token = str(uuid4())
        self._locks[lock_name] = token
        return token

    def release_lock(self, lock_name: str, token: str) -> bool:
        if self._locks.get(lock_name) == token:
            del self._locks[lock_name]
            return True
        return False

    def clear(self):
        self._data.clear()
        self._sets.clear()
        self._notifications.clear()
        self._workers.clear()
        self._locks.clear()


@pytest.fixture
def mock_redis() -> MockRedisClient:
    """Provide a mock Redis client."""
    return MockRedisClient()


# ============================================================================
# Repository Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def template_repository(db_session):
    """Create a template repository with test session."""
    from backend.app.domains.template.repository import TemplateRepository

    return TemplateRepository(db_session)


@pytest_asyncio.fixture
async def document_repository(db_session):
    """Create a document repository with test session."""
    from backend.app.domains.document.repository import DocumentRepository

    return DocumentRepository(db_session)


@pytest_asyncio.fixture
async def job_repository(db_session):
    """Create a job repository with test session."""
    from backend.app.domains.job.repository import JobRepository

    return JobRepository(db_session)


@pytest_asyncio.fixture
async def audit_repository(db_session):
    """Create an audit repository with test session."""
    from backend.app.domains.audit.repository import AuditRepository

    return AuditRepository(db_session)


@pytest_asyncio.fixture
async def section_repository(db_session):
    """Create a section repository with test session."""
    from backend.app.domains.section.repository import SectionRepository

    return SectionRepository(db_session)


# ============================================================================
# Service Fixtures (commented out - services need refactoring for tests)
# ============================================================================

# @pytest_asyncio.fixture
# async def template_service(template_repository, mock_storage, audit_repository):
#     """Create a template service with mocked storage."""
#     from backend.app.domains.template.service import TemplateService
#     return TemplateService(template_repository, mock_storage, audit_repository)


# @pytest_asyncio.fixture
# async def document_service(document_repository, mock_storage, audit_repository):
#     """Create a document service with mocked storage."""
#     from backend.app.domains.document.service import DocumentService
#     return DocumentService(document_repository, mock_storage, audit_repository)


# @pytest_asyncio.fixture
# async def job_service(job_repository):
#     """Create a job service."""
#     from backend.app.domains.job.service import JobService
#     return JobService(job_repository)


# ============================================================================
# Sample Data Factories
# ============================================================================


@pytest.fixture
def sample_template_data():
    """Factory for creating sample template data."""

    def _create(name: str = "Test Template"):
        return {"name": name}

    return _create


@pytest.fixture
def sample_docx_content():
    """Create a minimal valid .docx file content for testing."""
    from io import BytesIO

    def _create(text: str = "Sample document content"):
        doc = Document()
        doc.add_heading("Test Document", level=1)
        doc.add_paragraph(text)
        doc.add_paragraph("Another paragraph for testing.")

        # Add a table
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Header 1"
        table.cell(0, 1).text = "Header 2"
        table.cell(1, 0).text = "Value 1"
        table.cell(1, 1).text = "Value 2"

        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer.read()

    return _create


@pytest.fixture
def invalid_docx_content():
    """Create invalid .docx content for testing validation."""
    return b"This is not a valid docx file"


# ============================================================================
# Test Client Fixtures
# ============================================================================


@pytest.fixture
def test_client_sync():
    """Create a synchronous test client for FastAPI."""
    # Commented out - API tests require more setup
    # with patch('app.infrastructure.database.check_database_connectivity', return_value=True):
    #     with patch('app.infrastructure.redis.check_redis_connectivity', return_value=True):
    #         with patch('app.infrastructure.storage.check_storage_connectivity', return_value=True):
    #             from backend.app.main import app
    #             with TestClient(app) as client:
    #                 yield client
    yield None


# @pytest_asyncio.fixture
# async def test_client(async_engine, mock_storage, mock_redis) -> AsyncGenerator[AsyncClient, None]:
#     """Create an async test client with mocked dependencies."""
#     from httpx import AsyncClient, ASGITransport
#     from backend.app.main import app
#     from backend.app.api.deps import get_db, get_storage_service
#
#     async_session_maker = async_sessionmaker(
#         bind=async_engine,
#         class_=AsyncSession,
#         expire_on_commit=False,
#         autoflush=False,
#     )
#
#     async def override_get_db():
#         async with async_session_maker() as session:
#             yield session
#
#     def override_storage():
#         return mock_storage
#
#     app.dependency_overrides[get_db] = override_get_db
#     app.dependency_overrides[get_storage_service] = override_storage
#
#     transport = ASGITransport(app=app)
#     async with AsyncClient(transport=transport, base_url="http://test") as client:
#         yield client
#
#     app.dependency_overrides.clear()


# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "docker: marks tests that require Docker")
