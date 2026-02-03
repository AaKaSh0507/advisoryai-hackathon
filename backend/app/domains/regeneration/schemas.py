from datetime import datetime
from enum import Enum as PyEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RegenerationScope(str, PyEnum):
    SECTION = "SECTION"
    FULL = "FULL"


class RegenerationStrategy(str, PyEnum):
    REUSE_UNCHANGED = "REUSE_UNCHANGED"
    FORCE_ALL = "FORCE_ALL"


class RegenerationIntent(str, PyEnum):
    CONTENT_UPDATE = "CONTENT_UPDATE"
    CORRECTION = "CORRECTION"
    TEMPLATE_UPDATE = "TEMPLATE_UPDATE"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"


class RegenerationStatus(str, PyEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"


class SectionRegenerationTarget(BaseModel):
    section_id: int
    force: bool = False
    client_data_override: dict[str, Any] | None = None


class SectionRegenerationRequest(BaseModel):
    document_id: UUID
    target_sections: list[SectionRegenerationTarget] = Field(
        min_length=1, description="Sections to regenerate (must have at least one)"
    )
    intent: RegenerationIntent = RegenerationIntent.CONTENT_UPDATE
    strategy: RegenerationStrategy = RegenerationStrategy.REUSE_UNCHANGED
    client_data: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class FullRegenerationRequest(BaseModel):
    """Request for full document regeneration."""

    document_id: UUID
    intent: RegenerationIntent = RegenerationIntent.CONTENT_UPDATE
    client_data: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class TemplateUpdateRegenerationRequest(BaseModel):
    document_id: UUID
    new_template_version_id: UUID
    intent: RegenerationIntent = RegenerationIntent.TEMPLATE_UPDATE
    client_data: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class RegenerationSectionResult(BaseModel):
    section_id: int
    was_regenerated: bool
    was_reused: bool = False
    previous_content_hash: str | None = None
    new_content_hash: str | None = None
    error: str | None = None


class RegenerationResult(BaseModel):
    success: bool
    document_id: UUID
    previous_version_number: int | None = None
    new_version_number: int | None = None
    new_version_id: UUID | None = None
    scope: RegenerationScope
    intent: RegenerationIntent
    strategy: RegenerationStrategy | None = None
    status: RegenerationStatus
    section_results: list[RegenerationSectionResult] = Field(default_factory=list)
    sections_regenerated: int = 0
    sections_reused: int = 0
    sections_failed: int = 0
    error: str | None = None
    error_details: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    audit_log_ids: list[UUID] = Field(default_factory=list)
    correlation_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class VersionTransition(BaseModel):
    document_id: UUID
    old_version_number: int | None = None
    old_version_id: UUID | None = None
    new_version_number: int
    new_version_id: UUID
    scope: RegenerationScope
    intent: RegenerationIntent
    regenerated_section_ids: list[int] = Field(default_factory=list)
    reused_section_ids: list[int] = Field(default_factory=list)
    template_version_id: UUID
    timestamp: datetime


class RegenerationAuditPayload(BaseModel):
    document_id: UUID
    scope: RegenerationScope
    intent: RegenerationIntent
    strategy: RegenerationStrategy | None = None
    old_version: int | None = None
    new_version: int
    template_version_id: UUID
    regenerated_sections: list[int] = Field(default_factory=list)
    reused_sections: list[int] = Field(default_factory=list)
    section_content_hashes: dict[int, dict[str, str]] = Field(default_factory=dict)
    client_data_hash: str | None = None
    correlation_id: str | None = None
