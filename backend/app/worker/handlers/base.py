from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.job.models import Job


@dataclass
class HandlerContext:
    """Context passed to job handlers for accessing services."""

    session: AsyncSession
    job: Job


@dataclass
class HandlerResult:
    """Result returned from a job handler."""

    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    should_advance_pipeline: bool = True


class JobHandler(ABC):
    """Base class for job handlers."""

    @abstractmethod
    async def handle(self, context: HandlerContext) -> HandlerResult:
        """
        Execute the job.

        Args:
            context: Handler context with session and job information.

        Returns:
            HandlerResult indicating success/failure and any result data.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Handler name for logging and identification."""
        ...
