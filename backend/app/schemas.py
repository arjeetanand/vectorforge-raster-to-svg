from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import JobStatus


class VectorizationOptions(BaseModel):
    mode: Literal["line-art", "illustration"] = "line-art"
    color_count: int = Field(default=6, ge=2, le=16)
    smoothing: float = Field(default=0.5, ge=0, le=1)
    min_component_area: int = Field(default=24, ge=1, le=100_000)
    use_segmentation_model: bool = False


class ArtifactUrls(BaseModel):
    original: str | None = None
    svg: str | None = None
    preview: str | None = None
    comparison: str | None = None


class VectorizationResponse(BaseModel):
    id: str
    status: JobStatus
    source_filename: str
    options: VectorizationOptions
    source_width: int
    source_height: int
    model_used: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    artifacts: ArtifactUrls
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
