import uuid
from typing import Optional

import redis
from redis.exceptions import ConnectionError, RedisError

from backend.app.logging_config import get_logger

logger = get_logger("app.infrastructure.redis")
JOB_QUEUE_KEY = "jobs:pending"
JOB_NOTIFY_CHANNEL = "jobs:notifications"


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


class RedisClient:
    def __init__(self, redis_url: str):
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._pubsub: Optional[redis.client.PubSub] = None

    def close(self) -> None:
        if self._pubsub:
            self._pubsub.close()
        self._client.close()

    def ping(self) -> bool:
        try:
            return self._client.ping()
        except RedisError:
            return False

    def notify_job_created(self, job_id: uuid.UUID, job_type: str) -> None:
        try:
            message = f"{job_id}:{job_type}"
            self._client.publish(JOB_NOTIFY_CHANNEL, message)
            logger.debug(f"Published job notification: {message}")
        except RedisError as e:
            logger.warning(f"Failed to publish job notification: {e}")

    def subscribe_to_jobs(self) -> redis.client.PubSub:
        self._pubsub = self._client.pubsub()
        self._pubsub.subscribe(JOB_NOTIFY_CHANNEL)
        return self._pubsub

    def register_worker(self, worker_id: str, ttl_seconds: int = 60) -> None:
        key = f"workers:{worker_id}"
        self._client.setex(key, ttl_seconds, "active")

    def heartbeat(self, worker_id: str, ttl_seconds: int = 60) -> None:
        key = f"workers:{worker_id}"
        self._client.setex(key, ttl_seconds, "active")

    def unregister_worker(self, worker_id: str) -> None:
        key = f"workers:{worker_id}"
        self._client.delete(key)

    def get_active_workers(self) -> list[str]:
        keys = self._client.keys("workers:*")
        return [k.replace("workers:", "") for k in keys]

    def acquire_lock(self, name: str, ttl_seconds: int = 30) -> Optional[str]:
        token = str(uuid.uuid4())
        key = f"locks:{name}"
        if self._client.set(key, token, nx=True, ex=ttl_seconds):
            return token
        return None

    def release_lock(self, name: str, token: str) -> bool:
        key = f"locks:{name}"
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = self._client.eval(script, 1, key, token)
        return result == 1

    def extend_lock(self, name: str, token: str, ttl_seconds: int = 30) -> bool:
        key = f"locks:{name}"
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        result = self._client.eval(script, 1, key, token, ttl_seconds)
        return result == 1


_redis_client: Optional[RedisClient] = None


def get_redis_client(redis_url: str) -> RedisClient:
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient(redis_url)
    return _redis_client


def close_redis_client() -> None:
    global _redis_client
    if _redis_client:
        _redis_client.close()
        _redis_client = None
