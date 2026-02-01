from typing import Sequence, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.template.models import Template, TemplateVersion

class TemplateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, template: Template) -> Template:
        self.session.add(template)
        await self.session.flush()
        return template

    async def get_by_id(self, template_id: uuid.UUID) -> Optional[Template]:
        stmt = select(Template).where(Template.id == template_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
        
    async def list_all(self, skip: int = 0, limit: int = 100) -> Sequence[Template]:
        stmt = select(Template).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()
        
    async def delete(self, template: Template) -> None:
        await self.session.delete(template)
        await self.session.flush()

    async def create_version(self, version: TemplateVersion) -> TemplateVersion:
        self.session.add(version)
        await self.session.flush()
        return version

    async def get_version(self, template_id: uuid.UUID, version_number: int) -> Optional[TemplateVersion]:
        stmt = select(TemplateVersion).where(
            TemplateVersion.template_id == template_id,
            TemplateVersion.version_number == version_number
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_latest_version(self, template_id: uuid.UUID) -> Optional[TemplateVersion]:
        stmt = select(TemplateVersion).where(
            TemplateVersion.template_id == template_id
        ).order_by(TemplateVersion.version_number.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_versions(self, template_id: uuid.UUID) -> Sequence[TemplateVersion]:
        stmt = select(TemplateVersion).where(
            TemplateVersion.template_id == template_id
        ).order_by(TemplateVersion.version_number.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()
