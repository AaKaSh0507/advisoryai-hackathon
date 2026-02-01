from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class DocumentStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Document:
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    storage_path: Optional[str] = None
    status: DocumentStatus = DocumentStatus.PENDING
    content_type: Optional[str] = None
    size_bytes: int = 0
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
