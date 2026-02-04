import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Optional

from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.database import Base
from backend.app.infrastructure.datetime_utils import utc_now


class SectionType(str, PyEnum):
    STATIC = "STATIC"
    DYNAMIC = "DYNAMIC"


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("template_versions.id"), nullable=False
    )
    section_type: Mapped[SectionType] = mapped_column(
        SQLEnum(SectionType, name="section_type_enum"), nullable=False
    )
    structural_path: Mapped[str] = mapped_column(String, nullable=False)
    prompt_config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
