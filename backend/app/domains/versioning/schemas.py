import hashlib
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VersioningErrorCode(str, Enum):
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    DUPLICATE_VERSION = "DUPLICATE_VERSION"
    DUPLICATE_CONTENT = "DUPLICATE_CONTENT"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    STORAGE_FAILED = "STORAGE_FAILED"
    ROLLBACK_FAILED = "ROLLBACK_FAILED"
    INVALID_VERSION_NUMBER = "INVALID_VERSION_NUMBER"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    CONTENT_HASH_MISMATCH = "CONTENT_HASH_MISMATCH"


class VersioningError(BaseModel):
    code: VersioningErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class VersionCreateRequest(BaseModel):
    document_id: UUID
    content: bytes
    generation_metadata: dict[str, Any]
    content_hash: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def compute_content_hash(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    def get_content_hash(self) -> str:
        if self.content_hash:
            return self.content_hash
        return self.compute_content_hash()


class VersionCreateResult(BaseModel):
    success: bool
    document_id: UUID | None = None
    version_id: UUID | None = None
    version_number: int | None = None
    output_path: str | None = None
    content_hash: str | None = None
    is_duplicate: bool = False
    existing_version_number: int | None = None
    error: VersioningError | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class VersionMetadata(BaseModel):
    document_id: UUID
    version_number: int
    output_path: str
    content_hash: str
    file_size_bytes: int
    generation_metadata: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VersionHistoryEntry(BaseModel):
    version_id: UUID
    version_number: int
    output_path: str
    content_hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentVersionHistory(BaseModel):
    document_id: UUID
    current_version: int
    versions: list[VersionHistoryEntry]
    total_versions: int

    model_config = ConfigDict(from_attributes=True)
