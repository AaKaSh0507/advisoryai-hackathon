import asyncio
import signal
import sys
import uuid
from typing import Optional

from pydantic import ValidationError

from backend.app.config import get_settings
from backend.app.domains.job.models import JobType
from backend.app.domains.job.repository import JobRepository
from backend.app.domains.job.service import JobService
from backend.app.infrastructure.database import AsyncSessionLocal
from backend.app.infrastructure.redis import close_redis_client, get_redis_client
from backend.app.logging_config import get_logger, setup_logging
from backend.app.worker.handlers import HandlerContext, get_handler_for_job_type

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
POLL_INTERVAL_SECONDS = 1.0
HEARTBEAT_INTERVAL_SECONDS = 30.0
STUCK_JOB_CHECK_INTERVAL_SECONDS = 300.0  # 5 minutes
STUCK_JOB_TIMEOUT_MINUTES = 30


class Worker:
    def __init__(self):
        self._worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        self._running = False
        self._shutdown_event: Optional[asyncio.Event] = None
        self._redis = get_redis_client(settings.redis_url)

    @property
    def worker_id(self) -> str:
        return self._worker_id

    async def start(self) -> None:
        logger.info(f"Starting worker {self._worker_id} in {settings.app_env} environment")
        self._running = True
        self._shutdown_event = asyncio.Event()
        self._redis.register_worker(
            self._worker_id, ttl_seconds=int(HEARTBEAT_INTERVAL_SECONDS * 2)
        )
        for job_type in JobType:
            handler = get_handler_for_job_type(job_type)
            logger.info(f"Handler registered: {job_type.value} -> {handler.name}")

        logger.info("Worker started, entering main loop")
        await asyncio.gather(
            self._job_loop(),
            self._heartbeat_loop(),
            self._stuck_job_recovery_loop(),
        )

    async def _job_loop(self) -> None:
        while self._running:
            try:
                job_processed = await self._process_one_job()
                if not job_processed:
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
            except Exception as e:
                logger.error(f"Error in job loop: {e}", exc_info=True)
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

        logger.info("Job loop stopped")

    async def _heartbeat_loop(self) -> None:
        while self._running:
            try:
                self._redis.heartbeat(
                    self._worker_id, ttl_seconds=int(HEARTBEAT_INTERVAL_SECONDS * 2)
                )
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)

    async def _stuck_job_recovery_loop(self) -> None:
        while self._running:
            await asyncio.sleep(STUCK_JOB_CHECK_INTERVAL_SECONDS)
            try:
                await self._recover_stuck_jobs()
            except Exception as e:
                logger.error(f"Stuck job recovery failed: {e}", exc_info=True)

    async def _process_one_job(self) -> bool:
        async with AsyncSessionLocal() as session:
            try:
                repo = JobRepository(session)
                service = JobService(repo)
                job = await service.claim_job(self._worker_id)
                if not job:
                    return False

                logger.info(f"Processing job {job.id} ({job.job_type.value})")
                handler = get_handler_for_job_type(job.job_type)
                context = HandlerContext(session=session, job=job)
                try:
                    result = await handler.handle(context)
                    if result.success:
                        await service.complete_job(job.id, result.data)
                        await session.commit()
                        job = await service.get_job(job.id)
                        if result.should_advance_pipeline and job:
                            next_job = await service.advance_pipeline(job)
                            if next_job:
                                await session.commit()
                                self._redis.notify_job_created(next_job.id, next_job.job_type.value)

                        logger.info(f"Job {job.id} completed successfully")
                    else:
                        await service.fail_job(job.id, result.error or "Unknown error")
                        await session.commit()
                        logger.warning(f"Job {job.id} failed: {result.error}")

                except Exception as e:
                    logger.error(f"Job {job.id} handler exception: {e}", exc_info=True)
                    await service.fail_job(job.id, str(e))
                    await session.commit()

                return True

            except Exception as e:
                logger.error(f"Error processing job: {e}", exc_info=True)
                await session.rollback()
                return False

    async def _recover_stuck_jobs(self) -> None:
        lock_token = self._redis.acquire_lock("stuck_job_recovery", ttl_seconds=60)
        if not lock_token:
            return

        try:
            async with AsyncSessionLocal() as session:
                repo = JobRepository(session)
                service = JobService(repo)
                recovered_ids = await service.recover_stuck_jobs(STUCK_JOB_TIMEOUT_MINUTES)
                if recovered_ids:
                    await session.commit()
                    logger.info(f"Recovered {len(recovered_ids)} stuck jobs")
                    for job_id in recovered_ids:
                        job = await service.get_job(job_id)
                        if job:
                            self._redis.notify_job_created(job.id, job.job_type.value)
        finally:
            self._redis.release_lock("stuck_job_recovery", lock_token)

    def stop(self) -> None:
        logger.info(f"Worker {self._worker_id} shutdown requested")
        self._running = False
        if self._shutdown_event:
            self._shutdown_event.set()
        try:
            self._redis.unregister_worker(self._worker_id)
        except Exception as e:
            logger.warning(f"Failed to unregister worker: {e}")


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
    finally:
        close_redis_client()

    logger.info("Worker shutdown complete")


if __name__ == "__main__":
    main()
