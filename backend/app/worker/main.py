import asyncio
import signal
import sys
from typing import Optional

from pydantic import ValidationError

from backend.app.config import get_settings
from backend.app.logging_config import setup_logging, get_logger
from backend.app.worker.handlers import get_handler_for_job_type
from backend.app.domains.job.models import JobType

try:
    settings = get_settings()
except ValidationError as e:
    missing_fields = [err["loc"][0] for err in e.errors() if err["type"] == "missing"]
    if missing_fields:
        raise SystemExit(
            f"Missing required environment variables: {', '.join(str(f).upper() for f in missing_fields)}. "
            f"Please check your .env file or environment configuration."
        ) from e
    raise

setup_logging(settings.log_dir)
logger = get_logger("worker.main")


class Worker:
    def __init__(self):
        self._running = False
        self._shutdown_event: Optional[asyncio.Event] = None

    async def start(self) -> None:
        logger.info(f"Starting worker in {settings.app_env} environment")
        self._running = True
        self._shutdown_event = asyncio.Event()
        logger.info("Registering job handlers")
        for job_type in JobType:
            handler = get_handler_for_job_type(job_type)
            logger.info(f"Registered handler for job type: {job_type.value} -> {handler.__class__.__name__}")

        logger.info("Worker started successfully")
        await self._run_loop()

    async def _run_loop(self) -> None:
        logger.info("Worker loop started - waiting for shutdown signal")
        await self._shutdown_event.wait()
        logger.info("Worker loop stopped")

    def stop(self) -> None:
        logger.info("Worker shutdown requested")
        self._running = False
        if self._shutdown_event:
            self._shutdown_event.set()


worker = Worker()


def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}, initiating shutdown")
    worker.stop()


def main() -> None:
    logger.info("Initializing worker process")
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker failed with error: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Worker shutdown complete")


if __name__ == "__main__":
    main()
