from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID
from backend.app.domains.audit.models import AuditAction, AuditEntry


class AuditRepository(ABC):
    @abstractmethod
    async def create(self, entry: AuditEntry) -> AuditEntry:
        ...

    @abstractmethod
    async def query(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        action: Optional[AuditAction] = None,
        actor: Optional[str] = None,
        from_timestamp: Optional[datetime] = None,
        to_timestamp: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditEntry]:
        ...
