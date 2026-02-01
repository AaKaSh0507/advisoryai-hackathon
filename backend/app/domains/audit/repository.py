import uuid
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.audit.models import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, log: AuditLog) -> AuditLog:
        self.session.add(log)
        await self.session.flush()
        return log

    async def query(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        from_timestamp: Optional[datetime] = None,
        to_timestamp: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[AuditLog]:
        stmt = select(AuditLog)
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if from_timestamp:
            stmt = stmt.where(AuditLog.timestamp >= from_timestamp)
        if to_timestamp:
            stmt = stmt.where(AuditLog.timestamp <= to_timestamp)
        stmt = stmt.offset(skip).limit(limit).order_by(AuditLog.timestamp.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()
