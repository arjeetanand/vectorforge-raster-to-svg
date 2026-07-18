from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="VECTORFORGE_", extra="ignore"
    )

    app_name: str = "VectorForge"
    environment: str = "development"
    database_url: str = (
        "postgresql+psycopg://vectorforge:vectorforge@postgres:5432/vectorforge"
    )
    redis_url: str = "redis://redis:6379/0"
    artifact_root: Path = Field(default=Path("/app/data/vectorizations"))
    max_upload_bytes: int = 10 * 1024 * 1024
    max_image_pixels: int = 16_000_000
    max_processing_dimension: int = 2048
    artifact_ttl_hours: int = 24
    task_always_eager: bool = False
    optional_model_path: Path | None = None
    segmentation_model_sha256: str | None = None
    segmentation_model_device: str = "cpu"


@lru_cache
def get_settings() -> Settings:
    return Settings()
