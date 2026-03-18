from pydantic_settings import BaseSettings
from pydantic import PostgresDsn, field_validator
from functools import lru_cache
from typing import Optional
import logging


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-6"

    # Database
    database_url: PostgresDsn

    # AWS (optional for local dev — set these in .env only when deploying to AWS)
    aws_region: str = "us-east-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    s3_bucket_name: Optional[str] = None

    # Slack (optional — webhook URL for failure alerts)
    slack_webhook_url: Optional[str] = None

    # OpenAI embeddings (optional — falls back to local HuggingFace if not set)
    openai_api_key: Optional[str] = None

    # App
    log_level: str = "INFO"

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}, got '{v}'")
        return upper

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
