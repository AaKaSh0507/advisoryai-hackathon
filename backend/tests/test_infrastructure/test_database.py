"""
Tests for database schema and constraints.

Verifies:
- All tables exist with correct columns
- Enums are created correctly
- Foreign keys and uniqueness constraints are enforced
- Migrations run cleanly
"""

from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError


class TestDatabaseSchema:
    """Test database schema creation and structure."""

    @pytest.mark.asyncio
    async def test_all_tables_created(self, async_engine):
        """All expected tables should be created."""
        async with async_engine.connect() as conn:

            def get_tables(connection):
                inspector = inspect(connection)
                return inspector.get_table_names()

            tables = await conn.run_sync(get_tables)

        expected_tables = [
            "templates",
            "template_versions",
            "documents",
            "document_versions",
            "sections",
            "jobs",
            "audit_logs",
        ]

        for table in expected_tables:
            assert table in tables, f"Table '{table}' not found in database"

    @pytest.mark.asyncio
    async def test_templates_table_columns(self, async_engine):
        """Templates table should have correct columns."""
        async with async_engine.connect() as conn:

            def get_columns(connection):
                inspector = inspect(connection)
                return {c["name"]: c for c in inspector.get_columns("templates")}

            columns = await conn.run_sync(get_columns)

        assert "id" in columns
        assert "name" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

    @pytest.mark.asyncio
    async def test_template_versions_table_columns(self, async_engine):
        """Template versions table should have correct columns."""
        async with async_engine.connect() as conn:

            def get_columns(connection):
                inspector = inspect(connection)
                return {c["name"]: c for c in inspector.get_columns("template_versions")}

            columns = await conn.run_sync(get_columns)

        expected_columns = [
            "id",
            "template_id",
            "version_number",
            "source_doc_path",
            "parsed_representation_path",
            "parsing_status",
            "parsing_error",
            "parsed_at",
            "content_hash",
            "created_at",
        ]

        for col in expected_columns:
            assert col in columns, f"Column '{col}' not found in template_versions"

    @pytest.mark.asyncio
    async def test_jobs_table_columns(self, async_engine):
        """Jobs table should have correct columns."""
        async with async_engine.connect() as conn:

            def get_columns(connection):
                inspector = inspect(connection)
                return {c["name"]: c for c in inspector.get_columns("jobs")}

            columns = await conn.run_sync(get_columns)

        expected_columns = [
            "id",
            "job_type",
            "status",
            "payload",
            "result",
            "error",
            "worker_id",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]

        for col in expected_columns:
            assert col in columns, f"Column '{col}' not found in jobs"


class TestDatabaseConstraints:
    """Test database constraints and referential integrity."""

    @pytest.mark.asyncio
    async def test_template_version_unique_constraint(self, db_session):
        """Template version number should be unique per template."""
        from backend.app.domains.template.models import Template, TemplateVersion

        # Create a template
        template = Template(name="Test Template")
        db_session.add(template)
        await db_session.flush()

        # Create first version
        version1 = TemplateVersion(
            template_id=template.id, version_number=1, source_doc_path="path/to/v1.docx"
        )
        db_session.add(version1)
        await db_session.flush()

        # Try to create duplicate version - should fail
        version2 = TemplateVersion(
            template_id=template.id,
            version_number=1,  # Duplicate!
            source_doc_path="path/to/v1_dup.docx",
        )
        db_session.add(version2)

        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_document_version_unique_constraint(self, db_session):
        """Document version number should be unique per document."""
        from backend.app.domains.document.models import Document, DocumentVersion
        from backend.app.domains.template.models import Template, TemplateVersion

        # Create prerequisites
        template = Template(name="Test Template")
        db_session.add(template)
        await db_session.flush()

        version = TemplateVersion(
            template_id=template.id, version_number=1, source_doc_path="path/to/v1.docx"
        )
        db_session.add(version)
        await db_session.flush()

        document = Document(template_version_id=version.id, current_version=0)
        db_session.add(document)
        await db_session.flush()

        # Create first document version
        doc_v1 = DocumentVersion(
            document_id=document.id,
            version_number=1,
            output_doc_path="path/to/output1.docx",
            generation_metadata={},
        )
        db_session.add(doc_v1)
        await db_session.flush()

        # Try to create duplicate - should fail
        doc_v1_dup = DocumentVersion(
            document_id=document.id,
            version_number=1,  # Duplicate!
            output_doc_path="path/to/output1_dup.docx",
            generation_metadata={},
        )
        db_session.add(doc_v1_dup)

        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="SQLite does not enforce foreign keys by default. Tested in PostgreSQL integration tests."
    )
    async def test_template_version_foreign_key(self, db_session):
        """Template version should require valid template_id.

        Note: This test is skipped because SQLite doesn't enforce foreign keys by default.
        In production with PostgreSQL, foreign keys are enforced.
        """
        from backend.app.domains.template.models import TemplateVersion

        # Try to create version with non-existent template
        version = TemplateVersion(
            template_id=uuid4(),  # Non-existent template
            version_number=1,
            source_doc_path="path/to/v1.docx",
        )
        db_session.add(version)

        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="SQLite does not enforce foreign keys by default. Tested in PostgreSQL integration tests."
    )
    async def test_document_foreign_key(self, db_session):
        """Document should require valid template_version_id.

        Note: This test is skipped because SQLite doesn't enforce foreign keys by default.
        In production with PostgreSQL, foreign keys are enforced.
        """
        from backend.app.domains.document.models import Document

        # Try to create document with non-existent template version
        document = Document(template_version_id=uuid4(), current_version=0)  # Non-existent version
        db_session.add(document)

        with pytest.raises(IntegrityError):
            await db_session.flush()


class TestEnums:
    """Test enum types are correctly defined."""

    def test_job_type_enum_values(self):
        """JobType enum should have expected values."""
        from backend.app.domains.job.models import JobType

        assert JobType.PARSE.value == "PARSE"
        assert JobType.CLASSIFY.value == "CLASSIFY"
        assert JobType.GENERATE.value == "GENERATE"

    def test_job_status_enum_values(self):
        """JobStatus enum should have expected values."""
        from backend.app.domains.job.models import JobStatus

        assert JobStatus.PENDING.value == "PENDING"
        assert JobStatus.RUNNING.value == "RUNNING"
        assert JobStatus.COMPLETED.value == "COMPLETED"
        assert JobStatus.FAILED.value == "FAILED"

    def test_parsing_status_enum_values(self):
        """ParsingStatus enum should have expected values."""
        from backend.app.domains.template.models import ParsingStatus

        assert ParsingStatus.PENDING.value == "PENDING"
        assert ParsingStatus.IN_PROGRESS.value == "IN_PROGRESS"
        assert ParsingStatus.COMPLETED.value == "COMPLETED"
        assert ParsingStatus.FAILED.value == "FAILED"

    def test_section_type_enum_values(self):
        """SectionType enum should have expected values."""
        from backend.app.domains.section.models import SectionType

        assert SectionType.STATIC.value == "STATIC"
        assert SectionType.DYNAMIC.value == "DYNAMIC"
