from backend.app.domains.job.models import JobType
from backend.app.worker.handlers.base import HandlerContext, HandlerResult, JobHandler
from backend.app.worker.handlers.classification import ClassificationHandler
from backend.app.worker.handlers.generation_pipeline import GenerationPipelineHandler
from backend.app.worker.handlers.parsing import ParsingHandler

_handlers: dict[JobType, JobHandler] = {
    JobType.PARSE: ParsingHandler(),
    JobType.CLASSIFY: ClassificationHandler(),
    JobType.GENERATE: GenerationPipelineHandler(),
}


def get_handler_for_job_type(job_type: JobType) -> JobHandler:
    handler = _handlers.get(job_type)
    if not handler:
        raise ValueError(f"No handler registered for job type: {job_type}")
    return handler


__all__ = [
    "get_handler_for_job_type",
    "JobHandler",
    "HandlerContext",
    "HandlerResult",
]
