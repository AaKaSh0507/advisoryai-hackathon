import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.infrastructure.database import Base


class ParsingStatus(str, PyEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    versions: Mapped[list["TemplateVersion"]] = relationship(
        "TemplateVersion", back_populates="template", cascade="all, delete-orphan"
    )


class TemplateVersion(Base):
    __tablename__ = "template_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("templates.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_doc_path: Mapped[str] = mapped_column(String, nullable=False)
    parsed_representation_path: Mapped[str | None] = mapped_column(String, nullable=True)

    parsing_status: Mapped[ParsingStatus] = mapped_column(
        SQLEnum(ParsingStatus, name="parsing_status_enum"),
        nullable=False,
        default=ParsingStatus.PENDING,
    )
    parsing_error: Mapped[str | None] = mapped_column(String, nullable=True)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256 hash

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    template: Mapped["Template"] = relationship("Template", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("template_id", "version_number", name="uq_template_version"),
    )

    @property
    def is_parsed(self) -> bool:
        return bool(self.parsing_status == ParsingStatus.COMPLETED)

    @property
    def is_parsing_failed(self) -> bool:
        return bool(self.parsing_status == ParsingStatus.FAILED)
