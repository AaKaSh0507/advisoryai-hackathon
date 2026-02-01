from typing import Any

from backend.app.domains.job.models import Job
from backend.app.worker.handlers.base import JobHandler
from backend.app.logging_config import get_logger

logger = get_logger("worker.handlers.parsing")


class ParsingHandler(JobHandler):
    @property
    def name(self) -> str:
        return "ParsingHandler"

    async def handle(self, job: Job) -> dict[str, Any]:
        logger.info(f"Parsing handler invoked for job {job.id}")
        return {
            "status": "placeholder",
            "message": "Parsing handler not yet implemented",
            "job_id": str(job.id),
        }
