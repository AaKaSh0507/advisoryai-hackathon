import uuid
from datetime import datetime
from enum import Enum as PyEnum

from backend.app.infrastructure.database import Base
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class ParsingStatus(str, PyEnum):
    """Status of template parsing."""

    PENDING = "PENDING"  # Not yet parsed
    IN_PROGRESS = "IN_PROGRESS"  # Parsing in progress
    COMPLETED = "COMPLETED"  # Successfully parsed
    FAILED = "FAILED"  # Parsing failed


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

    # Parsing status tracking
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
        """Check if this version has been successfully parsed."""
        return self.parsing_status == ParsingStatus.COMPLETED

    @property
    def is_parsing_failed(self) -> bool:
        """Check if parsing failed."""
        return self.parsing_status == ParsingStatus.FAILED
