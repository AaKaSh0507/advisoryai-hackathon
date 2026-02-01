from typing import Sequence, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.section.models import Section

class SectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_batch(self, sections: list[Section]) -> list[Section]:
        self.session.add_all(sections)
        await self.session.flush()
        return sections

    async def get_by_template_version_id(self, template_version_id: uuid.UUID) -> Sequence[Section]:
        stmt = select(Section).where(Section.template_version_id == template_version_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()
