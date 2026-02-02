import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.template.models import ParsingStatus, Template, TemplateVersion


class TemplateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, template: Template) -> Template:
        self.session.add(template)
        await self.session.flush()
        return template

    async def get_by_id(self, template_id: uuid.UUID) -> Template | None:
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

    async def get_version(
        self, template_id: uuid.UUID, version_number: int
    ) -> TemplateVersion | None:
        stmt = select(TemplateVersion).where(
            TemplateVersion.template_id == template_id,
            TemplateVersion.version_number == version_number,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_version_by_id(self, version_id: uuid.UUID) -> TemplateVersion | None:
        stmt = select(TemplateVersion).where(TemplateVersion.id == version_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_version(self, template_id: uuid.UUID) -> TemplateVersion | None:
        stmt = (
            select(TemplateVersion)
            .where(TemplateVersion.template_id == template_id)
            .order_by(TemplateVersion.version_number.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_versions(self, template_id: uuid.UUID) -> Sequence[TemplateVersion]:
        stmt = (
            select(TemplateVersion)
            .where(TemplateVersion.template_id == template_id)
            .order_by(TemplateVersion.version_number.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_parsing_status(
        self,
        version_id: uuid.UUID,
        status: ParsingStatus,
        error: str | None = None,
        parsed_path: str | None = None,
        content_hash: str | None = None,
    ) -> TemplateVersion | None:
        version = await self.get_version_by_id(version_id)
        if not version:
            return None

        version.parsing_status = status
        version.parsing_error = error

        if status == ParsingStatus.COMPLETED:
            version.parsed_at = datetime.utcnow()
            if parsed_path:
                version.parsed_representation_path = parsed_path
            if content_hash:
                version.content_hash = content_hash

        await self.session.flush()
        return version

    async def mark_parsing_in_progress(self, version_id: uuid.UUID) -> TemplateVersion | None:
        return await self.update_parsing_status(version_id, ParsingStatus.IN_PROGRESS)

    async def mark_parsing_completed(
        self,
        version_id: uuid.UUID,
        parsed_path: str,
        content_hash: str,
    ) -> TemplateVersion | None:
        return await self.update_parsing_status(
            version_id,
            ParsingStatus.COMPLETED,
            parsed_path=parsed_path,
            content_hash=content_hash,
        )

    async def mark_parsing_failed(
        self,
        version_id: uuid.UUID,
        error: str,
    ) -> TemplateVersion | None:
        return await self.update_parsing_status(version_id, ParsingStatus.FAILED, error=error)
