from backend.app.domains.job.models import JobType
from backend.app.worker.handlers.base import JobHandler
from backend.app.worker.handlers.parsing import ParsingHandler
from backend.app.worker.handlers.classification import ClassificationHandler
from backend.app.worker.handlers.generation import GenerationHandler


_handlers: dict[JobType, JobHandler] = {
    JobType.PARSING: ParsingHandler(),
    JobType.CLASSIFICATION: ClassificationHandler(),
    JobType.GENERATION: GenerationHandler(),
}


def get_handler_for_job_type(job_type: JobType) -> JobHandler:
    handler = _handlers.get(job_type)
    if not handler:
        raise ValueError(f"No handler registered for job type: {job_type}")
    return handler


__all__ = ["get_handler_for_job_type", "JobHandler"]
