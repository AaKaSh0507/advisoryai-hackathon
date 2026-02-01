from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from backend.app.domains.audit.models import AuditAction


class AuditQuery(BaseModel):
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    action: Optional[AuditAction] = None
    actor: Optional[str] = None
    from_timestamp: Optional[datetime] = None
    to_timestamp: Optional[datetime] = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=1000)


class AuditEntryResponse(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    action: AuditAction
    actor: Optional[str]
    changes: Optional[dict[str, Any]]
    timestamp: datetime

    model_config = {"from_attributes": True}
