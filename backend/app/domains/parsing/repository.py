from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.parsing.schemas import ParsedDocument
from backend.app.domains.template.repository import TemplateRepository
from backend.app.infrastructure.storage import StorageService
from backend.app.logging_config import get_logger

logger = get_logger("app.domains.parsing.repository")


class ParsedDocumentRepository:
    def __init__(self, session: AsyncSession, storage: StorageService):
        self.session = session
        self.storage = storage

    async def get_by_template_version_id(self, template_version_id: UUID) -> ParsedDocument | None:
        try:
            template_repo = TemplateRepository(self.session)
            version = await template_repo.get_version_by_id(template_version_id)
            if not version:
                logger.warning(f"Template version {template_version_id} not found")
                return None
            if not version.parsed_doc_path:
                logger.warning(f"No parsed document path for version {template_version_id}")
                return None
            logger.info(f"Retrieving parsed document from {version.parsed_doc_path}")
            parsed_data = self.storage.get_file(version.parsed_doc_path)
            if not parsed_data:
                logger.warning(f"Parsed document not found at {version.parsed_doc_path}")
                return None
            import json

            parsed_dict = json.loads(parsed_data)
            parsed_doc = ParsedDocument(**parsed_dict)
            logger.info(
                f"Loaded parsed document for version {template_version_id}: "
                f"{len(parsed_doc.blocks)} blocks"
            )

            return parsed_doc

        except Exception as e:
            logger.error(
                f"Failed to retrieve parsed document for {template_version_id}: {e}", exc_info=True
            )
            return None
