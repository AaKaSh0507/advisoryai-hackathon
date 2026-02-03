from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentCreate(BaseModel):
    template_version_id: UUID


class DocumentUpdateTemplateVersion(BaseModel):
    """Request to update a document's template version."""

    new_template_version_id: UUID


class DocumentResponse(BaseModel):
    id: UUID
    template_version_id: UUID
    current_version: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentVersionResponse(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    output_doc_path: str
    generation_metadata: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
