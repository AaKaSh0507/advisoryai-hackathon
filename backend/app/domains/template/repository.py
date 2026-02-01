from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from backend.app.domains.template.models import Template


class TemplateRepository(ABC):
    @abstractmethod
    async def get_by_id(self, template_id: UUID) -> Optional[Template]:
        ...

    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Template]:
        ...

    @abstractmethod
    async def create(self, template: Template) -> Template:
        ...

    @abstractmethod
    async def update(self, template: Template) -> Template:
        ...

    @abstractmethod
    async def delete(self, template_id: UUID) -> bool:
        ...
