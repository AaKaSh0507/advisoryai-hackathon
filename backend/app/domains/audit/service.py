from typing import Any, Sequence
from uuid import UUID

from backend.app.domains.audit.models import AuditLog
from backend.app.domains.audit.schemas import AuditQuery
from backend.app.domains.audit.repository import AuditRepository


class AuditService:
    def __init__(self, repo: AuditRepository):
        self.repo = repo

    async def log_action(
        self,
        entity_type: str,
        entity_id: UUID,
        action: str,
        metadata: dict[str, Any],
    ) -> AuditLog:
        log = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            metadata_=metadata,
        )
        return await self.repo.create(log)

    async def query_audit_log(self, query: AuditQuery) -> Sequence[AuditLog]:
        return await self.repo.query(
            entity_type=query.entity_type,
            entity_id=query.entity_id,
            action=query.action,
            from_timestamp=query.from_timestamp,
            to_timestamp=query.to_timestamp,
            skip=query.skip,
            limit=query.limit,
        )
