"""Deterministic raster-to-SVG processing primitives."""

from .image import DecodedImage, ImageDecodeError, decode_image
from .quality import build_quality_report
from .segmentation import MaskResult, foreground_mask
from .types import VectorizationOptions, VectorizationResult
from .vectorize import VectorizationOutput, vectorize_image
from .vectorizer import vectorize

__all__ = [
    "DecodedImage",
    "ImageDecodeError",
    "MaskResult",
    "VectorizationOptions",
    "VectorizationResult",
    "VectorizationOutput",
    "decode_image",
    "build_quality_report",
    "foreground_mask",
    "vectorize",
    "vectorize_image",
]
