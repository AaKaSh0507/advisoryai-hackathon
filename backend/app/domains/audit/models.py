from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4


class AuditAction(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"


@dataclass
class AuditEntry:
    id: UUID = field(default_factory=uuid4)
    entity_type: str = ""
    entity_id: UUID = field(default_factory=uuid4)
    action: AuditAction = AuditAction.READ
    actor: Optional[str] = None
    changes: Optional[dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
