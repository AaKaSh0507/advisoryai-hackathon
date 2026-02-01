from typing import Any, Optional, Sequence
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
            metadata_=metadata
        )
        return await self.repo.create(log)

    async def query_audit_log(self, query: AuditQuery) -> Sequence[AuditLog]:
        # Implement filtering in repository if needed
        # For now return empty or implement basic query in repo
        # Repo currently only has create.
        # Minimal viable: return empty list or add query_all to repo
        return []
