import io
import json
import uuid
from typing import Any, BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

from backend.app.config import Settings
from backend.app.logging_config import get_logger

logger = get_logger("app.infrastructure.storage")


class StorageService:
    def __init__(self, settings: Settings):
        config = Config(connect_timeout=2, read_timeout=2, retries={"max_attempts": 1})
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=config,
        )
        self.bucket_name = settings.s3_bucket_name

    def upload_template_source(
        self, template_id: uuid.UUID, version: int, file_obj: BinaryIO
    ) -> str:
        key = f"templates/{template_id}/{version}/source.docx"
        self._upload_file(
            key,
            file_obj,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        return key

    def upload_template_parsed(
        self, template_id: uuid.UUID, version: int, file_obj: BinaryIO
    ) -> str:
        key = f"templates/{template_id}/{version}/parsed.json"
        self._upload_file(key, file_obj, content_type="application/json")
        return key

    def upload_template_parsed_json(
        self, template_id: uuid.UUID, version: int, parsed_data: dict[str, Any]
    ) -> str:
        json_bytes = json.dumps(parsed_data, indent=2, default=str).encode("utf-8")
        file_obj = io.BytesIO(json_bytes)
        return self.upload_template_parsed(template_id, version, file_obj)

    def get_template_source(self, template_id: uuid.UUID, version: int) -> bytes | None:
        key = f"templates/{template_id}/{version}/source.docx"
        return self.get_file(key)

    def get_template_parsed(self, template_id: uuid.UUID, version: int) -> dict[str, Any] | None:
        key = f"templates/{template_id}/{version}/parsed.json"
        content = self.get_file(key)
        if content:
            try:
                return json.loads(content.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.error(f"Failed to parse JSON from {key}: {e}")
                return None
        return None

    def template_source_exists(self, template_id: uuid.UUID, version: int) -> bool:
        key = f"templates/{template_id}/{version}/source.docx"
        return self.file_exists(key)

    def template_parsed_exists(self, template_id: uuid.UUID, version: int) -> bool:
        key = f"templates/{template_id}/{version}/parsed.json"
        return self.file_exists(key)

    def upload_document_output(
        self, document_id: uuid.UUID, version: int, file_obj: BinaryIO
    ) -> str:
        key = f"documents/{document_id}/{version}/output.docx"
        self._upload_file(
            key,
            file_obj,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        return key

    def get_file(self, key: str) -> bytes | None:
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read()
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                logger.debug(f"File not found: {key}")
            else:
                logger.error(f"Failed to get file {key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get file {key}: {e}")
            return None

    def file_exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404":
                return False
            logger.error(f"Error checking file existence {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error checking file existence {key}: {e}")
            return False

    def delete_file(self, key: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Deleted file {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {key}: {e}")
            return False

    def _upload_file(self, key: str, file_obj: BinaryIO, content_type: str | None = None):
        try:
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)

            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type

            self.client.upload_fileobj(file_obj, self.bucket_name, key, ExtraArgs=extra_args)
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
