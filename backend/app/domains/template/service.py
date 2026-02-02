from typing import BinaryIO, Optional, Sequence
from uuid import UUID

from backend.app.domains.audit.models import AuditLog
from backend.app.domains.audit.repository import AuditRepository
from backend.app.domains.template.models import Template, TemplateVersion
from backend.app.domains.template.repository import TemplateRepository
from backend.app.domains.template.schemas import TemplateCreate, TemplateUpdate
from backend.app.infrastructure.storage import StorageService


class TemplateService:
    def __init__(
        self, repo: TemplateRepository, storage: StorageService, audit_repo: AuditRepository
    ):
        self.repo = repo
        self.storage = storage
        self.audit_repo = audit_repo

    async def get_template(self, template_id: UUID) -> Optional[Template]:
        return await self.repo.get_by_id(template_id)

    async def list_templates(self, skip: int = 0, limit: int = 100) -> Sequence[Template]:
        return await self.repo.list_all(skip=skip, limit=limit)

    async def create_template(self, data: TemplateCreate) -> Template:
        template = Template(name=data.name)
        created_template = await self.repo.create(template)
        audit_log = AuditLog(
            entity_type="TEMPLATE",
            entity_id=created_template.id,
            action="CREATE",
            metadata_={"name": data.name},
        )
        await self.audit_repo.create(audit_log)
        return created_template

    async def update_template(self, template_id: UUID, data: TemplateUpdate) -> Optional[Template]:
        template = await self.repo.get_by_id(template_id)
        if not template:
            return None
        if data.name:
            template.name = data.name
        await self.repo.session.flush()
        return template

    async def delete_template(self, template_id: UUID) -> bool:
        template = await self.repo.get_by_id(template_id)
        if not template:
            return False
        await self.repo.delete(template)
        return True

    async def create_template_version(
        self, template_id: UUID, file_obj: BinaryIO
    ) -> Optional[TemplateVersion]:
        template = await self.repo.get_by_id(template_id)
        if not template:
            return None

        latest_version = await self.repo.get_latest_version(template_id)
        version_number = (latest_version.version_number + 1) if latest_version else 1
        source_path = self.storage.upload_template_source(
            template_id=template_id, version=version_number, file_obj=file_obj
        )
        version = TemplateVersion(
            template_id=template_id,
            version_number=version_number,
            source_doc_path=source_path,
        )
        created_version = await self.repo.create_version(version)
        audit_log = AuditLog(
            entity_type="TEMPLATE_VERSION",
            entity_id=created_version.id,
            action="CREATE",
            metadata_={
                "template_id": str(template_id),
                "version_number": version_number,
                "source_doc_path": source_path,
            },
        )
        await self.audit_repo.create(audit_log)

        return created_version
