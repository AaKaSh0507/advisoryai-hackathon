import redis
from redis.exceptions import ConnectionError, RedisError

from backend.app.logging_config import get_logger

logger = get_logger("app.infrastructure.redis")


def check_redis_connectivity(redis_url: str) -> bool:
    try:
        client = redis.from_url(redis_url)
        client.ping()
        client.close()
        logger.info("Redis connectivity check passed")
        return True
    except ConnectionError as e:
        logger.error(f"Redis connectivity check failed: {e}")
        return False
    except RedisError as e:
        logger.error(f"Redis error during connectivity check: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during Redis connectivity check: {e}")
        return False
