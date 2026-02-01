from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter

from backend.app.domains.audit.models import AuditAction
from backend.app.domains.audit.schemas import (
    AuditEntryResponse,
    AuditQuery,
)
from backend.app.domains.audit.service import AuditService

router = APIRouter()
service = AuditService()


@router.get("", response_model=list[AuditEntryResponse])
async def query_audit_log(
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    action: Optional[AuditAction] = None,
    actor: Optional[str] = None,
    from_timestamp: Optional[datetime] = None,
    to_timestamp: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[AuditEntryResponse]:
    query = AuditQuery(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        skip=skip,
        limit=limit,
    )
    entries = await service.query_audit_log(query)
    return [AuditEntryResponse.model_validate(e) for e in entries]
