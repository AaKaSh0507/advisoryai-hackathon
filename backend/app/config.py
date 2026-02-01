from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_env: str = Field(
        ...,
        description="Application environment (development, staging, production)",
    )

    database_url: str = Field(
        ...,
        description="PostgreSQL connection string",
    )

    redis_url: str = Field(
        ...,
        description="Redis connection string",
    )

    s3_endpoint_url: str = Field(
        ...,
        description="S3-compatible endpoint URL",
    )
    s3_access_key: str = Field(
        ...,
        description="S3 access key",
    )
    s3_secret_key: str = Field(
        ...,
        description="S3 secret key",
    )
    s3_bucket_name: str = Field(
        ...,
        description="S3 bucket name",
    )

    log_dir: str = Field(
        default="./logs",
        description="Directory for log files",
    )


def get_settings() -> Settings:
    return Settings()
