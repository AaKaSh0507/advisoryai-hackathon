import boto3
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

from backend.app.logging_config import get_logger

logger = get_logger("app.infrastructure.storage")


def check_storage_connectivity(
    endpoint_url: str,
    access_key: str,
    secret_key: str,
    bucket_name: str,
) -> bool:
    try:
        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        client.head_bucket(Bucket=bucket_name)
        logger.info(f"Storage connectivity check passed for bucket: {bucket_name}")
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "404":
            logger.error(f"Storage bucket not found: {bucket_name}")
        elif error_code == "403":
            logger.error(f"Storage access denied for bucket: {bucket_name}")
        else:
            logger.error(f"Storage connectivity check failed: {e}")
        return False
    except EndpointConnectionError as e:
        logger.error(f"Storage endpoint connection failed: {e}")
        return False
    except NoCredentialsError as e:
        logger.error(f"Storage credentials missing: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during storage connectivity check: {e}")
        return False
