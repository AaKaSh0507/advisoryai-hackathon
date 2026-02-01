from abc import ABC, abstractmethod
from typing import Any

from backend.app.domains.job.models import Job


class JobHandler(ABC):
    @abstractmethod
    async def handle(self, job: Job) -> dict[str, Any]:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...
