import io
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError
from typing import BinaryIO, Optional
import uuid

from backend.app.logging_config import get_logger
from backend.app.config import Settings

logger = get_logger("app.infrastructure.storage")

class StorageService:
    def __init__(self, settings: Settings):
        config = Config(
            connect_timeout=2,
            read_timeout=2,
            retries={"max_attempts": 1}
        )
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=config,
        )
        self.bucket_name = settings.s3_bucket_name

    def upload_template_source(self, template_id: uuid.UUID, version: int, file_obj: BinaryIO) -> str:
        key = f"templates/{template_id}/{version}/source.docx"
        self._upload_file(key, file_obj)
        return key

    def upload_template_parsed(self, template_id: uuid.UUID, version: int, file_obj: BinaryIO) -> str:
        key = f"templates/{template_id}/{version}/parsed.json"
        self._upload_file(key, file_obj)
        return key

    def upload_document_output(self, document_id: uuid.UUID, version: int, file_obj: BinaryIO) -> str:
        key = f"documents/{document_id}/{version}/output.docx"
        self._upload_file(key, file_obj)
        return key
    
    def get_file(self, key: str) -> Optional[bytes]:
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"Failed to get file {key}: {e}")
            return None

    def _upload_file(self, key: str, file_obj: BinaryIO):
        try:
            # reset file pointer to beginning if possible
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)
            self.client.upload_fileobj(file_obj, self.bucket_name, key)
            logger.info(f"Uploaded file to {key}")
        except Exception as e:
            logger.error(f"Failed to upload file to {key}: {e}")
            raise e

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
