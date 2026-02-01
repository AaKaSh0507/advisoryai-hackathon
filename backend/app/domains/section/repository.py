from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID
from backend.app.domains.section.models import Section


class SectionRepository(ABC):
    @abstractmethod
    async def get_by_id(self, section_id: UUID) -> Optional[Section]:
        ...

    @abstractmethod
    async def get_by_template(
        self, template_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Section]:
        ...

    @abstractmethod
    async def create(self, section: Section) -> Section:
        ...

    @abstractmethod
    async def update(self, section: Section) -> Section:
        ...

    @abstractmethod
    async def delete(self, section_id: UUID) -> bool:
        ...

    @abstractmethod
    async def reorder(self, template_id: UUID, section_ids: list[UUID]) -> bool:
        ...
