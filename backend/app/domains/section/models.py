from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class Section:
    id: UUID = field(default_factory=uuid4)
    template_id: UUID = field(default_factory=uuid4)
    name: str = ""
    content: Optional[str] = None
    order: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
