from typing import Optional, Sequence
from uuid import UUID

from backend.app.domains.section.models import Section
from backend.app.domains.section.schemas import SectionCreate
from backend.app.domains.section.repository import SectionRepository

class SectionService:
    def __init__(self, repo: SectionRepository):
        self.repo = repo

    async def create_section(self, data: SectionCreate) -> Section:
        section = Section(
            template_version_id=data.template_version_id,
            section_type=data.section_type,
            structural_path=data.structural_path,
            prompt_config=data.prompt_config
        )
        # We need to wrap single creation in list for batch repo method or add single create to repo.
        # SectionRepository has create_batch.
        # Let's use create_batch for single item
        created = await self.repo.create_batch([section])
        return created[0]

    async def get_sections_by_template_version(self, template_version_id: UUID) -> Sequence[Section]:
        return await self.repo.get_by_template_version_id(template_version_id)
