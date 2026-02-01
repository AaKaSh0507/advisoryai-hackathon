import uuid
from datetime import datetime
from typing import Optional, Any
from enum import Enum as PyEnum

from sqlalchemy import String, Integer, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from backend.app.infrastructure.database import Base

class SectionType(str, PyEnum):
    STATIC = "STATIC"
    DYNAMIC = "DYNAMIC"

class Section(Base):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("template_versions.id"), nullable=False)
    section_type: Mapped[SectionType] = mapped_column(SQLEnum(SectionType, name="section_type_enum"), nullable=False)
    structural_path: Mapped[str] = mapped_column(String, nullable=False)
    prompt_config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
