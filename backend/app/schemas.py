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


class SvgComplexity(BaseModel):
    command_count: int = Field(ge=0)
    path_data_characters: int = Field(ge=0)
    level: Literal["low", "medium", "high"]


class ModelMetadata(BaseModel):
    requested: bool
    provider: str
    model_id: str | None = None
    version: str | None = None
    architecture: str | None = None
    checkpoint: str | None = None
    checkpoint_sha256: str | None = None
    fallback_reason: str | None = None


class QualityReport(BaseModel):
    """Explainable output-health indicators, not a model-accuracy claim."""

    score: int = Field(ge=0, le=100)
    level: Literal["good", "review", "unsupported"]
    warnings: list[str] = Field(default_factory=list)
    foreground_coverage: float = Field(ge=0, le=1)
    path_count: int = Field(ge=0)
    retained_color_count: int = Field(ge=0)
    removed_component_count: int = Field(ge=0)
    visual_similarity: float = Field(ge=0, le=1)
    svg_complexity: SvgComplexity
    model_metadata: ModelMetadata | None = None
    input_kind: str | None = None


class VectorizationResponse(BaseModel):
    id: str
    status: JobStatus
    source_filename: str
    options: VectorizationOptions
    source_width: int
    source_height: int
    model_used: str | None = None
    quality: QualityReport | None = None
    error_code: str | None = None
    error_detail: str | None = None
    artifacts: ArtifactUrls
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class BatchVectorizationResponse(BaseModel):
    id: str
    status: Literal["queued", "processing", "completed", "partial", "failed"]
    total_count: int = Field(ge=1)
    completed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    items: list[VectorizationResponse]
    created_at: datetime
    updated_at: datetime
