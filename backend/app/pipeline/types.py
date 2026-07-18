"""Shared, framework-independent pipeline types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

VectorizationMode = Literal["line-art", "illustration"]


@dataclass(frozen=True)
class VectorizationOptions:
    """User-facing controls after API validation.

    ``smoothing`` is the Catmull--Rom control-point strength, not an arbitrary
    SVG post-process.  A value of zero keeps simplified polygons as line paths.
    """

    mode: VectorizationMode = "line-art"
    colors: int = 6
    smoothing: float = 0.45
    min_component_area: int = 24

    def __post_init__(self) -> None:
        if self.mode not in ("line-art", "illustration"):
            raise ValueError("mode must be 'line-art' or 'illustration'")
        if not 2 <= self.colors <= 16:
            raise ValueError("colors must be between 2 and 16")
        if not 0.0 <= self.smoothing <= 1.0:
            raise ValueError("smoothing must be between 0 and 1")
        if self.min_component_area < 1:
            raise ValueError("min_component_area must be positive")


@dataclass(frozen=True)
class VectorizationResult:
    """The SVG and diagnostics a caller may persist with a job."""

    svg: str
    width: int
    height: int
    model_used: str
    foreground_mask: np.ndarray
    preview_rgb: np.ndarray
    path_count: int
