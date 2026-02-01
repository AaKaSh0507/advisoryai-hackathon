from typing import Optional
from uuid import UUID
from backend.app.domains.section.models import Section
from backend.app.domains.section.schemas import SectionCreate, SectionUpdate


class SectionService:
    async def get_section(self, section_id: UUID) -> Optional[Section]:
        return None

    async def list_sections_by_template(
        self, template_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Section]:
        return []

    async def create_section(self, data: SectionCreate) -> Section:
        return Section(
            template_id=data.template_id,
            name=data.name,
            content=data.content,
            order=data.order,
        )

    async def update_section(
        self, section_id: UUID, data: SectionUpdate
    ) -> Optional[Section]:
        return None

    async def delete_section(self, section_id: UUID) -> bool:
        return False

    async def reorder_sections(self, template_id: UUID, section_ids: list[UUID]) -> bool:
        return False
