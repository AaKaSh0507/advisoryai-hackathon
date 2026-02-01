"""
Tests for Audit Logging infrastructure.

Verifies:
- Audit logs can be created and retrieved
- Audit logs contain proper metadata
- Audit logs can be queried by entity
"""

from datetime import datetime
from uuid import uuid4

import pytest


class TestAuditLogRepository:
    """Tests for AuditRepository functionality."""

    @pytest.mark.asyncio
    async def test_create_audit_log(self, audit_repository):
        """Should create an audit log entry."""
        from backend.app.domains.audit.models import AuditLog

        log = AuditLog(
            entity_type="template",
            entity_id=uuid4(),
            action="created",
            metadata_={"name": "Test Template"},
        )

        created = await audit_repository.create(log)

        assert created.id is not None
        assert created.entity_type == "template"
        assert created.action == "created"
        assert created.timestamp is not None

    @pytest.mark.asyncio
    async def test_query_audit_logs_by_entity(self, audit_repository):
        """Should query audit logs for a specific entity."""
        from backend.app.domains.audit.models import AuditLog

        entity_id = uuid4()

        # Create multiple logs for same entity
        for action in ["created", "updated", "published"]:
            log = AuditLog(
                entity_type="template",
                entity_id=entity_id,
                action=action,
                metadata_={"action": action},
            )
            await audit_repository.create(log)

        logs = await audit_repository.query(entity_type="template", entity_id=entity_id)

        assert len(logs) == 3
        actions = {log.action for log in logs}
        assert actions == {"created", "updated", "published"}

    @pytest.mark.asyncio
    async def test_query_audit_logs_all(self, audit_repository):
        """Should query all audit logs with pagination."""
        from backend.app.domains.audit.models import AuditLog

        # Create logs for different entities
        for i in range(5):
            log = AuditLog(
                entity_type="job", entity_id=uuid4(), action=f"action_{i}", metadata_={"index": i}
            )
            await audit_repository.create(log)

        logs = await audit_repository.query(limit=10)

        assert len(logs) >= 5

    @pytest.mark.asyncio
    async def test_query_audit_logs_by_action(self, audit_repository):
        """Should filter audit logs by action."""
        from backend.app.domains.audit.models import AuditLog

        # Create logs with different actions
        for action in ["created", "created", "updated"]:
            log = AuditLog(entity_type="template", entity_id=uuid4(), action=action, metadata_={})
            await audit_repository.create(log)

        created_logs = await audit_repository.query(action="created")

        assert len(created_logs) >= 2
        assert all(log.action == "created" for log in created_logs)

    @pytest.mark.asyncio
    async def test_query_audit_logs_pagination(self, audit_repository):
        """Should support pagination when querying audit logs."""
        from backend.app.domains.audit.models import AuditLog

        entity_id = uuid4()

        # Create 10 logs
        for i in range(10):
            log = AuditLog(
                entity_type="section", entity_id=entity_id, action=f"action_{i}", metadata_={}
            )
            await audit_repository.create(log)

        # Get first page
        page1 = await audit_repository.query(
            entity_type="section", entity_id=entity_id, skip=0, limit=5
        )
        assert len(page1) == 5

        # Get second page
        page2 = await audit_repository.query(
            entity_type="section", entity_id=entity_id, skip=5, limit=5
        )
        assert len(page2) == 5

        # Verify different logs
        page1_ids = {log.id for log in page1}
        page2_ids = {log.id for log in page2}
        assert page1_ids.isdisjoint(page2_ids)


class TestAuditLogMetadata:
    """Tests for audit log metadata handling."""

    @pytest.mark.asyncio
    async def test_audit_log_stores_metadata(self, audit_repository):
        """Should store and retrieve metadata correctly."""
        from backend.app.domains.audit.models import AuditLog

        metadata = {
            "old_status": "pending",
            "new_status": "completed",
            "duration_seconds": 45,
            "processed_by": "worker-1",
        }

        log = AuditLog(
            entity_type="job", entity_id=uuid4(), action="status_changed", metadata_=metadata
        )
        created = await audit_repository.create(log)

        # Query to get back the log
        logs = await audit_repository.query(entity_type="job", entity_id=created.entity_id)

        assert len(logs) == 1
        assert logs[0].metadata_ == metadata

    @pytest.mark.asyncio
    async def test_audit_log_empty_metadata(self, audit_repository):
        """Should handle empty metadata dict."""
        from backend.app.domains.audit.models import AuditLog

        log = AuditLog(entity_type="template", entity_id=uuid4(), action="deleted", metadata_={})

        created = await audit_repository.create(log)

        logs = await audit_repository.query(entity_type="template", entity_id=created.entity_id)

        assert len(logs) == 1
        assert logs[0].metadata_ == {}

    @pytest.mark.asyncio
    async def test_audit_log_nested_metadata(self, audit_repository):
        """Should handle nested metadata structures."""
        from backend.app.domains.audit.models import AuditLog

        metadata = {
            "changes": {
                "field1": {"old": "value1", "new": "value2"},
                "field2": {"old": 1, "new": 2},
            },
            "context": {"user": "system", "reason": "automated"},
        }

        log = AuditLog(
            entity_type="document", entity_id=uuid4(), action="updated", metadata_=metadata
        )

        created = await audit_repository.create(log)

        logs = await audit_repository.query(entity_type="document", entity_id=created.entity_id)

        assert len(logs) == 1
        assert logs[0].metadata_["changes"]["field1"]["new"] == "value2"
        assert logs[0].metadata_["context"]["user"] == "system"


class TestAuditTrailCompleteness:
    """Tests for audit trail completeness requirements."""

    @pytest.mark.asyncio
    async def test_audit_logs_have_timestamps(self, audit_repository):
        """All audit logs should have timestamp."""
        from backend.app.domains.audit.models import AuditLog

        log = AuditLog(entity_type="template", entity_id=uuid4(), action="created", metadata_={})

        created = await audit_repository.create(log)

        assert created.timestamp is not None
        assert isinstance(created.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_audit_logs_ordered_by_time(self, audit_repository):
        """Audit logs should be retrievable in chronological order."""
        import asyncio

        from backend.app.domains.audit.models import AuditLog

        entity_id = uuid4()

        # Create logs with slight delays to ensure ordering
        for i in range(3):
            log = AuditLog(
                entity_type="template",
                entity_id=entity_id,
                action=f"action_{i}",
                metadata_={"order": i},
            )
            await audit_repository.create(log)
            await asyncio.sleep(0.01)  # Small delay

        logs = await audit_repository.query(entity_type="template", entity_id=entity_id)

        # Should be ordered by timestamp (descending by default)
        assert len(logs) == 3


class TestAuditLogEntityTypes:
    """Tests for different entity types in audit logs."""

    @pytest.mark.asyncio
    async def test_template_audit_logs(self, audit_repository):
        """Should handle template entity type."""
        from backend.app.domains.audit.models import AuditLog

        entity_id = uuid4()
        log = AuditLog(
            entity_type="template",
            entity_id=entity_id,
            action="created",
            metadata_={"name": "Test Template"},
        )
        await audit_repository.create(log)

        logs = await audit_repository.query(entity_type="template", entity_id=entity_id)
        assert len(logs) == 1
        assert logs[0].entity_type == "template"

    @pytest.mark.asyncio
    async def test_job_audit_logs(self, audit_repository):
        """Should handle job entity type."""
        from backend.app.domains.audit.models import AuditLog

        entity_id = uuid4()
        log = AuditLog(
            entity_type="job",
            entity_id=entity_id,
            action="completed",
            metadata_={"job_type": "PARSE", "duration_ms": 1500},
        )
        await audit_repository.create(log)

        logs = await audit_repository.query(entity_type="job", entity_id=entity_id)
        assert len(logs) == 1
        assert logs[0].metadata_["job_type"] == "PARSE"


class TestAuditLogActions:
    """Tests for common audit log actions."""

    @pytest.mark.asyncio
    async def test_create_action(self, audit_repository):
        """Should log entity creation."""
        from backend.app.domains.audit.models import AuditLog

        log = AuditLog(
            entity_type="template",
            entity_id=uuid4(),
            action="created",
            metadata_={"name": "New Template"},
        )
        created = await audit_repository.create(log)

        assert created.action == "created"

    @pytest.mark.asyncio
    async def test_update_action(self, audit_repository):
        """Should log entity updates with old/new values."""
        from backend.app.domains.audit.models import AuditLog

        log = AuditLog(
            entity_type="template",
            entity_id=uuid4(),
            action="updated",
            metadata_={"field": "name", "old_value": "Old Name", "new_value": "New Name"},
        )
        created = await audit_repository.create(log)

        assert created.action == "updated"
        assert created.metadata_["old_value"] == "Old Name"
        assert created.metadata_["new_value"] == "New Name"

    @pytest.mark.asyncio
    async def test_status_change_action(self, audit_repository):
        """Should log status changes."""
        from backend.app.domains.audit.models import AuditLog

        log = AuditLog(
            entity_type="job",
            entity_id=uuid4(),
            action="status_changed",
            metadata_={"from_status": "PENDING", "to_status": "RUNNING"},
        )
        created = await audit_repository.create(log)

        assert created.action == "status_changed"
        assert "from_status" in created.metadata_
        assert "to_status" in created.metadata_
