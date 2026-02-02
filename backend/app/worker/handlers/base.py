from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.job.models import Job


@dataclass
class HandlerContext:
    session: AsyncSession
    job: Job


@dataclass
class HandlerResult:
    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    should_advance_pipeline: bool = True


class JobHandler(ABC):
    @abstractmethod
    async def handle(self, context: HandlerContext) -> HandlerResult: ...

    @property
    @abstractmethod
    def name(self) -> str: ...
