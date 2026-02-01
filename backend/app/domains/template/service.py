from typing import Optional
from uuid import UUID
from backend.app.domains.template.models import Template
from backend.app.domains.template.schemas import TemplateCreate, TemplateUpdate


class TemplateService:
    async def get_template(self, template_id: UUID) -> Optional[Template]:
        return None

    async def list_templates(self, skip: int = 0, limit: int = 100) -> list[Template]:
        return []

    async def create_template(self, data: TemplateCreate) -> Template:
        return Template(name=data.name, description=data.description)

    async def update_template(
        self, template_id: UUID, data: TemplateUpdate
    ) -> Optional[Template]:
        return None

    async def delete_template(self, template_id: UUID) -> bool:
        return False
