from typing import Optional, Sequence, BinaryIO
from uuid import UUID

from backend.app.domains.document.models import Document
from backend.app.domains.document.schemas import DocumentCreate
from backend.app.domains.document.repository import DocumentRepository
from backend.app.infrastructure.storage import StorageService
from backend.app.domains.audit.repository import AuditRepository
from backend.app.domains.audit.models import AuditLog

class DocumentService:
    def __init__(
        self, 
        repo: DocumentRepository, 
        storage: StorageService,
        audit_repo: AuditRepository
    ):
        self.repo = repo
        self.storage = storage
        self.audit_repo = audit_repo

    async def get_document(self, document_id: UUID) -> Optional[Document]:
        return await self.repo.get_by_id(document_id)
        
    async def create_document(self, data: DocumentCreate) -> Document:
        doc = Document(
            template_version_id=data.template_version_id,
            current_version=0
        )
        created_doc = await self.repo.create(doc)

        # Audit Log
        audit_log = AuditLog(
            entity_type="DOCUMENT",
            entity_id=created_doc.id,
            action="CREATE",
            metadata_={"template_version_id": str(data.template_version_id)}
        )
        await self.audit_repo.create(audit_log)

        return created_doc

    async def create_document_version(
        self, document_id: UUID, file_obj: BinaryIO, metadata: dict
    ) -> Optional[Document]:
        doc = await self.repo.get_by_id(document_id)
        if not doc:
            return None

        latest_version = await self.repo.get_latest_version(document_id)
        version_number = (latest_version.version_number + 1) if latest_version else 1

        # Upload to storage
        output_path = self.storage.upload_document_output(
            document_id=document_id, version=version_number, file_obj=file_obj
        )

        # Create version in DB
        version = DocumentVersion(
            document_id=document_id,
            version_number=version_number,
            output_doc_path=output_path,
            generation_metadata=metadata,
        )
        created_version = await self.repo.create_version(version)

        # Update document current version
        doc.current_version = version_number
        await self.repo.session.flush()

        # Audit Log
        audit_log = AuditLog(
            entity_type="DOCUMENT_VERSION",
            entity_id=created_version.id,
            action="CREATE",
            metadata_={
                "document_id": str(document_id),
                "version_number": version_number,
                "output_doc_path": output_path,
            },
        )
        await self.audit_repo.create(audit_log)

        return doc
