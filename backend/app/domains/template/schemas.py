from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)

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
    parsed_representation_path: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
