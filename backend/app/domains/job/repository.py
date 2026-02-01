from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from backend.app.domains.job.models import Job, JobStatus


class JobRepository(ABC):
    @abstractmethod
    async def get_by_id(self, job_id: UUID) -> Optional[Job]:
        ...

    @abstractmethod
    async def get_all(
        self, status: Optional[JobStatus] = None, skip: int = 0, limit: int = 100
    ) -> list[Job]:
        ...

    @abstractmethod
    async def create(self, job: Job) -> Job:
        ...

    @abstractmethod
    async def update(self, job: Job) -> Job:
        ...

    @abstractmethod
    async def get_next_pending(self) -> Optional[Job]:
        ...
