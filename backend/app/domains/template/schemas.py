from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.template.models import ParsingStatus


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class TemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)


class TemplateResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TemplateVersionResponse(BaseModel):
    id: UUID
    template_id: UUID
    version_number: int
    source_doc_path: str
    parsed_representation_path: str | None = None
    parsing_status: ParsingStatus
    parsing_error: str | None = None
    parsed_at: datetime | None = None
    content_hash: str | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TemplateVersionDetailResponse(TemplateVersionResponse):
    is_parsed: bool = False
    is_parsing_failed: bool = False
    model_config = ConfigDict(from_attributes=True)
