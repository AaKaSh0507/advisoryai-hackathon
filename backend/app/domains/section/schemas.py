from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from backend.app.domains.section.models import SectionType


class SectionCreate(BaseModel):
    template_version_id: UUID
    section_type: SectionType
    structural_path: str
    prompt_config: Optional[dict[str, Any]] = None


class SectionResponse(BaseModel):
    id: int
    template_version_id: UUID
    section_type: SectionType
    structural_path: str
    prompt_config: Optional[dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
