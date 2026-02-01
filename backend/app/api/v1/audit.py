from datetime import datetime
from typing import Optional, Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from backend.app.domains.audit.schemas import (
    AuditLogResponse,
    AuditQuery,
)
from backend.app.domains.audit.service import AuditService
from backend.app.api.deps import get_audit_service

router = APIRouter()
AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]

@router.get("", response_model=list[AuditLogResponse])
async def query_audit_log(
    service: AuditServiceDep,
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    action: Optional[str] = None,
    from_timestamp: Optional[datetime] = None,
    to_timestamp: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[AuditLogResponse]:
    query = AuditQuery(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        skip=skip,
        limit=limit,
    )
    entries = await service.query_audit_log(query)
    return [AuditLogResponse.model_validate(e) for e in entries]
