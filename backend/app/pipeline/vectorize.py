"""Filesystem facade used by the asynchronous worker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from PIL import Image

from app.core.config import get_settings
from app.ml.manifest import (
    DEFAULT_SEGMENTATION_MODEL_ID,
    DEEPLABV3_MOBILENET_V3_LARGE,
    get_model_artifact,
)
from app.ml.segmentation import select_configured_segmentation_model

from .image import decode_image
from .types import VectorizationOptions
from .vectorizer import vectorize


class NoVectorPathsError(ValueError):
    """Raised when no editable SVG paths survive vectorization filtering."""


@dataclass(frozen=True)
class VectorizationOutput:
    """Named artifact locations produced for one isolated job directory."""

    svg_path: Path
    preview_path: Path
    comparison_path: Path
    model_used: str
    quality: dict[str, Any]

    @property
    def quality_report(self) -> dict[str, Any]:
        """Compatibility alias for callers using the descriptive old name."""

        return self.quality


def vectorize_image(
    source_path: Path, output_dir: Path, options: dict[str, Any]
) -> VectorizationOutput:
    """Vectorize one file and write SVG, preview, and comparison artifacts."""

    settings = get_settings()
    decoded = decode_image(
        source_path.read_bytes(),
        max_bytes=settings.max_upload_bytes,
        max_pixels=settings.max_image_pixels,
        processing_longest_side=settings.max_processing_dimension,
    )
    use_model = bool(options.get("use_segmentation_model", False))
    selection = select_configured_segmentation_model(
        use_model,
        settings.optional_model_path,
        device=settings.segmentation_model_device,
        expected_sha256=settings.segmentation_model_sha256,
    )
    result = vectorize(
        decoded.rgb,
        _options_from_mapping(options),
        alpha=decoded.alpha,
        segmentation_model=selection.model,
    )
    if result.path_count == 0:
        # A PNG preview can still resemble the source even when foreground or
        # component filtering left no eligible contour. Never present that as
        # a successful vectorization with an empty downloadable SVG.
        raise NoVectorPathsError(
            "No editable vector paths were detected in this image."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    svg_path = output_dir / "vector.svg"
    preview_path = output_dir / "preview.png"
    comparison_path = output_dir / "comparison.png"
    svg_path.write_text(result.svg, encoding="utf-8")
    Image.fromarray(result.preview_rgb, mode="RGB").save(preview_path, format="PNG")
    Image.fromarray(_comparison(decoded.rgb, result.preview_rgb), mode="RGB").save(
        comparison_path, format="PNG"
    )
    model_used = result.model_used
    # The CV primitive reports ``opencv`` consistently.  At this worker
    # boundary, enrich requested-but-unavailable/failed ML inference so job
    # metadata makes its deterministic fallback explicit.
    if use_model and model_used == "opencv":
        model_used = (
            f"opencv-fallback:{selection.fallback_reason or 'model-inference-failed'}"
        )
    quality = dict(result.quality)
    quality["model_used"] = model_used
    quality["model_metadata"] = _model_metadata(
        requested=use_model,
        model_used=model_used,
        fallback_reason=selection.fallback_reason,
        expected_sha256=settings.segmentation_model_sha256,
        model_id=selection.model_id,
    )
    return VectorizationOutput(
        svg_path, preview_path, comparison_path, model_used, quality
    )


def _options_from_mapping(options: Mapping[str, Any]) -> VectorizationOptions:
    colors = options.get("colors", options.get("color_count", 6))
    return VectorizationOptions(
        mode=options.get("mode", "line-art"),
        colors=int(colors),
        smoothing=float(options.get("smoothing", 0.45)),
        min_component_area=int(options.get("min_component_area", 24)),
    )


def _model_metadata(
    *,
    requested: bool,
    model_used: str,
    fallback_reason: str | None,
    expected_sha256: str | None,
    model_id: str = DEFAULT_SEGMENTATION_MODEL_ID,
) -> dict[str, str | bool | None]:
    """Return provenance that is safe to persist and display.

    Paths and raw load exceptions are intentionally excluded. A fine-tuned
    checkpoint can override the public checkpoint digest through settings, but
    remains clearly identified as operator-configured rather than silently
    presented as the TorchVision public weight.
    """

    try:
        artifact = get_model_artifact(model_id)
    except ValueError:
        artifact = DEEPLABV3_MOBILENET_V3_LARGE
    requested_model_id = model_id if requested else None
    configured_digest = expected_sha256 or artifact.sha256
    public_checkpoint = configured_digest == artifact.sha256
    requested_version = (
        artifact.version
        if requested and public_checkpoint
        else "operator-configured"
        if requested
        else None
    )
    if model_used == "torchvision":
        return {
            "requested": requested,
            "provider": "torchvision",
            "model_id": artifact.model_id,
            "version": requested_version,
            "architecture": artifact.architecture,
            "checkpoint": artifact.name
            if public_checkpoint
            else "operator-configured local checkpoint",
            "checkpoint_sha256": configured_digest,
            "fallback_reason": None,
        }
    if model_used.startswith("opencv-fallback:"):
        return {
            "requested": requested,
            "provider": "opencv",
            "model_id": requested_model_id,
            "version": requested_version,
            # Keep the reviewed requested-model identity even when the
            # worker falls back.  This explains which checkpoint was absent,
            # invalid, or failed without persisting a local path or traceback.
            "architecture": artifact.architecture if requested else None,
            "checkpoint": artifact.name
            if requested and public_checkpoint
            else "operator-configured local checkpoint"
            if requested
            else None,
            "checkpoint_sha256": configured_digest if requested else None,
            "fallback_reason": fallback_reason
            or model_used.removeprefix("opencv-fallback:"),
        }
    return {
        "requested": requested,
        "provider": model_used,
        "model_id": requested_model_id,
        "version": requested_version,
        "architecture": None,
        "checkpoint": None,
        "checkpoint_sha256": None,
        "fallback_reason": None,
    }


def _comparison(source_rgb: np.ndarray, preview_rgb: np.ndarray) -> np.ndarray:
    divider = np.full((source_rgb.shape[0], 2, 3), 210, dtype=np.uint8)
    return np.concatenate((source_rgb, divider, preview_rgb), axis=1)
