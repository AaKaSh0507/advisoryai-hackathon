from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from backend.app.domains.audit.models import AuditAction, AuditEntry
from backend.app.domains.audit.schemas import AuditQuery


class AuditService:
    async def log_action(
        self,
        entity_type: str,
        entity_id: UUID,
        action: AuditAction,
        actor: Optional[str] = None,
        changes: Optional[dict[str, Any]] = None,
    ) -> AuditEntry:
        return AuditEntry(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            changes=changes,
        )

    async def query_audit_log(self, query: AuditQuery) -> list[AuditEntry]:
        return []
