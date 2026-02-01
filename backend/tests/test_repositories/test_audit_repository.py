"""
Tests for Audit repository.

Verifies:
- Audit log creation
- Querying by entity
- Querying by action type
"""

import pytest


class TestAuditRepository:
    """Tests for AuditRepository."""

    @pytest.mark.asyncio
    async def test_create_audit_log(self, audit_repository, template_repository):
        """Should create an audit log entry."""
        from backend.app.domains.audit.models import AuditLog
        from backend.app.domains.template.models import Template

        template = Template(name="Test Template")
        await template_repository.create(template)

        log = AuditLog(
            entity_type="template",
            entity_id=template.id,
            action="created",
            metadata_={"name": "Test Template"},
        )
        created = await audit_repository.create(log)

        assert created.id is not None
        assert created.entity_type == "template"
        assert created.action == "created"
        assert created.timestamp is not None

    @pytest.mark.asyncio
    async def test_query_by_entity(self, audit_repository, template_repository):
        """Should query audit logs for a specific entity."""
        from backend.app.domains.audit.models import AuditLog
        from backend.app.domains.template.models import Template

        template = Template(name="Test Template")
        await template_repository.create(template)

        # Create multiple logs for same entity
        actions = ["created", "updated", "parsed"]
        for action in actions:
            log = AuditLog(
                entity_type="template", entity_id=template.id, action=action, metadata_={}
            )
            await audit_repository.create(log)

        logs = await audit_repository.query(entity_type="template", entity_id=template.id)

        assert len(logs) == 3

    @pytest.mark.asyncio
    async def test_query_by_action(self, audit_repository, template_repository):
        """Should query audit logs by action type."""
        from backend.app.domains.audit.models import AuditLog
        from backend.app.domains.template.models import Template

        # Create multiple templates with same action
        for i in range(3):
            template = Template(name=f"Template {i}")
            await template_repository.create(template)

            log = AuditLog(
                entity_type="template", entity_id=template.id, action="created", metadata_={}
            )
            await audit_repository.create(log)

        logs = await audit_repository.query(action="created")

        assert len(logs) == 3

    @pytest.mark.asyncio
    async def test_audit_logs_ordered_by_timestamp(self, audit_repository, template_repository):
        """Should return audit logs in chronological order (newest first)."""
        import asyncio

        from backend.app.domains.audit.models import AuditLog
        from backend.app.domains.template.models import Template

        template = Template(name="Test Template")
        await template_repository.create(template)

        # Create logs with slight delay
        for i in range(3):
            log = AuditLog(
                entity_type="template",
                entity_id=template.id,
                action=f"action_{i}",
                metadata_={"order": i},
            )
            await audit_repository.create(log)
            await asyncio.sleep(0.01)  # Small delay for timestamp ordering

        logs = await audit_repository.query(entity_type="template", entity_id=template.id)

        # Should be newest first
        assert logs[0].action == "action_2"
        assert logs[2].action == "action_0"

    @pytest.mark.asyncio
    async def test_audit_log_metadata_json(self, audit_repository, template_repository):
        """Should store complex JSON in metadata field."""
        from backend.app.domains.audit.models import AuditLog
        from backend.app.domains.template.models import Template

        template = Template(name="Test Template")
        await template_repository.create(template)

        complex_metadata = {
            "old_value": {"name": "Old Name"},
            "new_value": {"name": "New Name"},
            "changed_fields": ["name"],
        }

        log = AuditLog(
            entity_type="template",
            entity_id=template.id,
            action="updated",
            metadata_=complex_metadata,
        )
        await audit_repository.create(log)

        logs = await audit_repository.query(entity_type="template", entity_id=template.id)

        assert logs[0].metadata_ == complex_metadata

    @pytest.mark.asyncio
    async def test_query_with_pagination(self, audit_repository, template_repository):
        """Should support pagination in queries."""
        from backend.app.domains.audit.models import AuditLog
        from backend.app.domains.template.models import Template

        # Create multiple templates and logs
        for i in range(5):
            template = Template(name=f"Template {i}")
            await template_repository.create(template)

            log = AuditLog(
                entity_type="template", entity_id=template.id, action="created", metadata_={}
            )
            await audit_repository.create(log)

        # Test pagination
        paginated = await audit_repository.query(skip=2, limit=2)
        assert len(paginated) == 2

    @pytest.mark.asyncio
    async def test_query_empty_returns_empty_list(self, audit_repository):
        """Should return empty list when no matching audit logs."""
        logs = await audit_repository.query(entity_type="nonexistent")
        assert logs == []
