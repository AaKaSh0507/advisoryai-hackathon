from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    s3_region: str = Field(
        default="auto",
        description="S3 region (use 'auto' for Cloudflare R2)",
    )

    log_dir: str = Field(
        default="./logs",
        description="Directory for log files",
    )

    cors_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins",
    )

    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key for LLM-assisted structure inference",
    )
    openai_api_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API base URL (or compatible API endpoint)",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model to use for structure inference",
    )
    llm_inference_enabled: bool = Field(
        default=True,
        description="Enable LLM-assisted structure inference",
    )
    llm_confidence_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for applying LLM suggestions",
    )


def get_settings() -> Settings:
    return Settings()
