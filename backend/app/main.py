from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import ValidationError

from backend.app.api.v1 import router as api_v1_router
from backend.app.config import get_settings
from backend.app.infrastructure.database import check_database_connectivity
from backend.app.infrastructure.redis import check_redis_connectivity, get_redis_client
from backend.app.infrastructure.storage import check_storage_connectivity
from backend.app.logging_config import get_logger, setup_logging

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
logger = get_logger("app.main")


async def verify_infrastructure() -> dict:
    logger.info("Starting infrastructure connectivity verification")
    db_status = await check_database_connectivity()
    redis_status = check_redis_connectivity(settings.redis_url)
    storage_status = check_storage_connectivity(
        settings.s3_endpoint_url,
        settings.s3_access_key,
        settings.s3_secret_key,
        settings.s3_bucket_name,
    )

    results = {
        "database": db_status,
        "redis": redis_status,
        "storage": storage_status,
    }

    all_healthy = all(results.values())
    if all_healthy:
        logger.info("All infrastructure connectivity checks passed")
    else:
        failed = [k for k, v in results.items() if not v]
        logger.warning(f"Infrastructure connectivity checks failed for: {', '.join(failed)}")

    return results


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting Template Intelligence Engine in {settings.app_env} environment")
    connectivity = await verify_infrastructure()
    app.state.infrastructure_status = connectivity
    yield
    logger.info("Shutting down Template Intelligence Engine")


app = FastAPI(
    title="Template Intelligence Engine",
    description="AdvisoryAI Internal Platform - Job System and Pipeline Orchestration",
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(api_v1_router)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "healthy"}


@app.get("/health/infrastructure")
async def infrastructure_health() -> dict:
    return {
        "status": "healthy" if all(app.state.infrastructure_status.values()) else "degraded",
        "components": app.state.infrastructure_status,
    }


@app.get("/health/workers")
async def workers_health() -> dict:
    try:
        redis_client = get_redis_client(settings.redis_url)
        active_workers = redis_client.get_active_workers()
        return {
            "status": "healthy" if active_workers else "no_workers",
            "active_workers": active_workers,
            "count": len(active_workers),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "active_workers": [],
            "count": 0,
        }
