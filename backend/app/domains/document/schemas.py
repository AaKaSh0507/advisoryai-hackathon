from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
from backend.app.domains.document.models import DocumentStatus


class DocumentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    content_type: Optional[str] = None


class DocumentResponse(BaseModel):
    id: UUID
    name: str
    storage_path: Optional[str]
    status: DocumentStatus
    content_type: Optional[str]
    size_bytes: int
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentStatusResponse(BaseModel):
    id: UUID
    name: str
    status: DocumentStatus
    error_message: Optional[str]
    updated_at: datetime
