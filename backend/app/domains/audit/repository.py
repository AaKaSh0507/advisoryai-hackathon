import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.domains.audit.models import AuditLog

class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, log: AuditLog) -> AuditLog:
        self.session.add(log)
        await self.session.flush()
        return log
