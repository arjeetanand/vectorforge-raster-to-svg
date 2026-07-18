"""High-level classical raster-to-SVG conversion."""

from __future__ import annotations

import cv2
import numpy as np

from .colors import filter_components_with_diagnostics, quantize_rgb
from .contours import contour_to_svg_path, simplify_contour
from .quality import build_quality_report
from .segmentation import SegmentationModel, foreground_mask
from .svg import svg_document
from .types import VectorizationOptions, VectorizationResult


def vectorize(
    rgb: np.ndarray,
    options: VectorizationOptions | None = None,
    *,
    alpha: np.ndarray | None = None,
    segmentation_model: SegmentationModel | None = None,
) -> VectorizationResult:
    """Convert a uint8 RGB image to editable fill-path SVG.

    Line-art intentionally emits filled ink regions. It does not claim to infer
    centreline strokes, which is unreliable for hand-drawn or anti-aliased art.
    """

    options = options or VectorizationOptions()
    mask_result = foreground_mask(rgb, alpha, segmentation_model)
    if options.mode == "line-art":
        preview, layers, removed_component_count = _line_art_layers(
            rgb, mask_result.mask, options
        )
    else:
        preview, layers, removed_component_count = _illustration_layers(
            rgb, mask_result.mask, options
        )
    paths: list[tuple[str, str]] = []
    for binary, color in layers:
        paths.extend(_paths_for_mask(binary, color, options.smoothing))
    svg = svg_document(rgb.shape[1], rgb.shape[0], paths)
    return VectorizationResult(
        svg=svg,
        width=rgb.shape[1],
        height=rgb.shape[0],
        model_used=mask_result.source,
        foreground_mask=mask_result.mask,
        preview_rgb=preview,
        path_count=len(paths),
        quality=build_quality_report(
            source_rgb=rgb,
            preview_rgb=preview,
            foreground_mask=mask_result.mask,
            path_count=len(paths),
            retained_color_count=len(layers),
            removed_component_count=removed_component_count,
            svg_paths=[path for path, _ in paths],
            model_used=mask_result.source,
        ),
    )


def _line_art_layers(
    rgb: np.ndarray, foreground: np.ndarray, options: VectorizationOptions
) -> tuple[np.ndarray, list[tuple[np.ndarray, str]], int]:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    # Otsu selects dark ink on the usual light background. Foreground restricts
    # the result when alpha/model has supplied a reliable artwork region.
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink = cv2.bitwise_and(ink, foreground)
    filtered = filter_components_with_diagnostics(ink, options.min_component_area)
    ink = filtered.mask
    preview = np.full_like(rgb, 255)
    preview[ink > 0] = (0, 0, 0)
    layers = [(ink, "#111827")] if np.any(ink) else []
    return preview, layers, filtered.removed_component_count


def _illustration_layers(
    rgb: np.ndarray, foreground: np.ndarray, options: VectorizationOptions
) -> tuple[np.ndarray, list[tuple[np.ndarray, str]], int]:
    preview = quantize_rgb(rgb, options.colors, foreground)
    active_colours = np.unique(preview[foreground > 0].reshape(-1, 3), axis=0)
    layers: list[tuple[np.ndarray, str]] = []
    removed_component_count = 0
    for color in active_colours:
        layer = np.all(preview == color, axis=2).astype(np.uint8) * 255
        layer = cv2.bitwise_and(layer, foreground)
        filtered = filter_components_with_diagnostics(layer, options.min_component_area)
        layer = filtered.mask
        removed_component_count += filtered.removed_component_count
        if np.any(layer):
            layers.append((layer, _hex_color(color)))
    return preview, layers, removed_component_count


def _paths_for_mask(
    mask: np.ndarray, color: str, smoothing: float
) -> list[tuple[str, str]]:
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hierarchy is None:
        return []
    hierarchy = hierarchy[0]
    paths: list[tuple[str, str]] = []
    # Include every outer contour and its direct/indirect holes in a single
    # even-odd path. This makes donut-like logo features transparent in SVG.
    for index, contour in enumerate(contours):
        if hierarchy[index][3] != -1:
            continue
        pieces = [_simplified_path(contour, smoothing)]
        child = hierarchy[index][2]
        while child != -1:
            pieces.append(_simplified_path(contours[child], smoothing))
            child = hierarchy[child][0]
        path = " ".join(piece for piece in pieces if piece)
        if path:
            paths.append((path, color))
    return paths


def _simplified_path(contour: np.ndarray, smoothing: float) -> str:
    points = simplify_contour(contour, smoothing=smoothing)
    return contour_to_svg_path(points, smoothing=smoothing)


def _hex_color(color: np.ndarray) -> str:
    return "#" + "".join(f"{int(channel):02x}" for channel in color)
