import psycopg
from psycopg import OperationalError

from backend.app.logging_config import get_logger

logger = get_logger("app.infrastructure.database")


def check_database_connectivity(database_url: str) -> bool:
    try:
        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        logger.info("Database connectivity check passed")
        return True
    except OperationalError as e:
        logger.error(f"Database connectivity check failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during database connectivity check: {e}")
        return False

