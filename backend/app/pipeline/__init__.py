"""Deterministic raster-to-SVG processing primitives."""

from .image import DecodedImage, ImageDecodeError, decode_image
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
    "foreground_mask",
    "vectorize",
    "vectorize_image",
]
