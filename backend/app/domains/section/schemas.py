from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class SectionCreate(BaseModel):
    template_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    content: Optional[str] = None
    order: int = Field(default=0, ge=0)


class SectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = None
    order: Optional[int] = Field(None, ge=0)


class SectionReorder(BaseModel):
    section_ids: list[UUID] = Field(..., min_length=1)


class SectionResponse(BaseModel):
    id: UUID
    template_id: UUID
    name: str
    content: Optional[str]
    order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
