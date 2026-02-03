import io
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from backend.app.domains.audit.models import AuditLog
from backend.app.domains.audit.repository import AuditRepository
from backend.app.domains.versioning.repository import VersioningRepository
from backend.app.domains.versioning.schemas import (
    DocumentVersionHistory,
    VersionCreateRequest,
    VersionCreateResult,
    VersionHistoryEntry,
    VersioningError,
    VersioningErrorCode,
    VersionMetadata,
)
from backend.app.infrastructure.storage import StorageService
from backend.app.logging_config import get_logger

logger = get_logger("app.domains.versioning.service")


class DocumentVersioningService:
    def __init__(
        self,
        repository: VersioningRepository,
        storage: StorageService,
        audit_repo: AuditRepository,
    ):
        self.repository = repository
        self.storage = storage
        self.audit_repo = audit_repo

    async def create_version(self, request: VersionCreateRequest) -> VersionCreateResult:
        document = await self.repository.get_document(request.document_id)
        if not document:
            return VersionCreateResult(
                success=False,
                document_id=request.document_id,
                error=VersioningError(
                    code=VersioningErrorCode.DOCUMENT_NOT_FOUND,
                    message=f"Document {request.document_id} not found",
                    details={"document_id": str(request.document_id)},
                ),
            )

        content_hash = request.get_content_hash()

        existing_version = await self.repository.get_version_by_content_hash(
            request.document_id, content_hash
        )
        if existing_version:
            logger.info(
                f"Duplicate content detected for document {request.document_id}, "
                f"returning existing version {existing_version.version_number}"
            )
            return VersionCreateResult(
                success=True,
                document_id=request.document_id,
                version_id=existing_version.id,
                version_number=existing_version.version_number,
                output_path=existing_version.output_doc_path,
                content_hash=content_hash,
                is_duplicate=True,
                existing_version_number=existing_version.version_number,
                created_at=existing_version.created_at,
            )

        version_number = await self.repository.get_next_version_number(request.document_id)

        generation_metadata = {
            **request.generation_metadata,
            "content_hash": content_hash,
            "file_size_bytes": len(request.content),
        }

        output_path: str | None = None
        version_created = False
        storage_uploaded = False

        try:
            file_obj = io.BytesIO(request.content)
            output_path = self.storage.upload_document_output(
                document_id=request.document_id,
                version=version_number,
                file_obj=file_obj,
            )
            storage_uploaded = True

            if not self.storage.file_exists(output_path):
                return await self._handle_storage_failure(
                    request.document_id,
                    version_number,
                    output_path,
                    storage_uploaded,
                )

            document_version = await self.repository.create_version(
                document_id=request.document_id,
                version_number=version_number,
                output_path=output_path,
                generation_metadata=generation_metadata,
            )
            version_created = True

            await self.repository.update_current_version(document, version_number)

            await self._create_version_audit_log(
                document_version.id,
                request.document_id,
                version_number,
                output_path,
                content_hash,
            )

            await self._create_current_version_audit_log(
                request.document_id,
                version_number,
            )

            logger.info(f"Created version {version_number} for document {request.document_id}")

            return VersionCreateResult(
                success=True,
                document_id=request.document_id,
                version_id=document_version.id,
                version_number=version_number,
                output_path=output_path,
                content_hash=content_hash,
                is_duplicate=False,
                created_at=document_version.created_at,
            )

        except IntegrityError as e:
            logger.error(f"Integrity error creating version: {e}")
            await self._rollback_on_failure(
                request.document_id,
                version_number,
                output_path,
                storage_uploaded,
                version_created,
            )
            return VersionCreateResult(
                success=False,
                document_id=request.document_id,
                error=VersioningError(
                    code=VersioningErrorCode.DUPLICATE_VERSION,
                    message=f"Version {version_number} already exists for document",
                    details={
                        "document_id": str(request.document_id),
                        "version_number": version_number,
                    },
                ),
            )

        except Exception as e:
            logger.error(f"Error creating version: {e}")
            await self._rollback_on_failure(
                request.document_id,
                version_number,
                output_path,
                storage_uploaded,
                version_created,
            )
            return VersionCreateResult(
                success=False,
                document_id=request.document_id,
                error=VersioningError(
                    code=VersioningErrorCode.PERSISTENCE_FAILED,
                    message=f"Failed to create version: {str(e)}",
                    details={
                        "document_id": str(request.document_id),
                        "error": str(e),
                    },
                ),
            )

    async def _handle_storage_failure(
        self,
        document_id: UUID,
        version_number: int,
        output_path: str | None,
        storage_uploaded: bool,
    ) -> VersionCreateResult:
        if storage_uploaded and output_path:
            self.storage.delete_file(output_path)

        return VersionCreateResult(
            success=False,
            document_id=document_id,
            error=VersioningError(
                code=VersioningErrorCode.STORAGE_FAILED,
                message="Failed to persist document to storage",
                details={
                    "document_id": str(document_id),
                    "version_number": version_number,
                },
            ),
        )

    async def _rollback_on_failure(
        self,
        document_id: UUID,
        version_number: int,
        output_path: str | None,
        storage_uploaded: bool,
        version_created: bool,
    ) -> None:
        try:
            if storage_uploaded and output_path:
                self.storage.delete_file(output_path)
                logger.info(f"Rolled back storage for {output_path}")
        except Exception as rollback_error:
            logger.error(f"Failed to rollback storage: {rollback_error}")

    async def _create_version_audit_log(
        self,
        version_id: UUID,
        document_id: UUID,
        version_number: int,
        output_path: str,
        content_hash: str,
    ) -> None:
        audit_log = AuditLog(
            entity_type="DOCUMENT_VERSION",
            entity_id=version_id,
            action="CREATE",
            metadata_={
                "document_id": str(document_id),
                "version_number": version_number,
                "output_path": output_path,
                "content_hash": content_hash,
            },
        )
        await self.audit_repo.create(audit_log)

    async def _create_current_version_audit_log(
        self,
        document_id: UUID,
        version_number: int,
    ) -> None:
        audit_log = AuditLog(
            entity_type="DOCUMENT",
            entity_id=document_id,
            action="UPDATE_CURRENT_VERSION",
            metadata_={
                "document_id": str(document_id),
                "new_current_version": version_number,
            },
        )
        await self.audit_repo.create(audit_log)

    async def get_version(self, document_id: UUID, version_number: int) -> VersionMetadata | None:
        version = await self.repository.get_version(document_id, version_number)
        if not version:
            return None

        return VersionMetadata(
            document_id=version.document_id,
            version_number=version.version_number,
            output_path=version.output_doc_path,
            content_hash=version.generation_metadata.get("content_hash", ""),
            file_size_bytes=version.generation_metadata.get("file_size_bytes", 0),
            generation_metadata=version.generation_metadata,
            created_at=version.created_at,
        )

    async def get_version_history(self, document_id: UUID) -> DocumentVersionHistory | None:
        document = await self.repository.get_document(document_id)
        if not document:
            return None

        versions = await self.repository.list_versions(document_id)

        version_entries = [
            VersionHistoryEntry(
                version_id=v.id,
                version_number=v.version_number,
                output_path=v.output_doc_path,
                content_hash=v.generation_metadata.get("content_hash", ""),
                created_at=v.created_at,
            )
            for v in versions
        ]

        return DocumentVersionHistory(
            document_id=document_id,
            current_version=document.current_version,
            versions=version_entries,
            total_versions=len(version_entries),
        )

    async def version_exists(self, document_id: UUID, version_number: int) -> bool:
        return await self.repository.version_exists(document_id, version_number)

    async def get_current_version(self, document_id: UUID) -> VersionMetadata | None:
        document = await self.repository.get_document(document_id)
        if not document or document.current_version == 0:
            return None

        return await self.get_version(document_id, document.current_version)

    async def get_version_content(self, document_id: UUID, version_number: int) -> bytes | None:
        version = await self.repository.get_version(document_id, version_number)
        if not version:
            return None

        return self.storage.get_document_output(document_id, version_number)

    async def verify_version_integrity(self, document_id: UUID, version_number: int) -> bool:
        version = await self.repository.get_version(document_id, version_number)
        if not version:
            return False

        content = self.storage.get_document_output(document_id, version_number)
        if not content:
            return False

        import hashlib

        computed_hash = hashlib.sha256(content).hexdigest()
        stored_hash = version.generation_metadata.get("content_hash", "")

        return bool(computed_hash == stored_hash)
