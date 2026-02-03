"""
Regeneration domain module.

Provides services for:
- Section-level regeneration (targeted, partial)
- Full document regeneration
- Template version update handling

All regeneration creates new immutable versions while preserving history.
"""

from backend.app.domains.regeneration.schemas import (
    FullRegenerationRequest,
    RegenerationIntent,
    RegenerationResult,
    RegenerationScope,
    RegenerationStatus,
    RegenerationStrategy,
    SectionRegenerationRequest,
)
from backend.app.domains.regeneration.service import RegenerationService

__all__ = [
    "RegenerationIntent",
    "RegenerationScope",
    "RegenerationStrategy",
    "SectionRegenerationRequest",
    "FullRegenerationRequest",
    "RegenerationResult",
    "RegenerationStatus",
    "RegenerationService",
]
