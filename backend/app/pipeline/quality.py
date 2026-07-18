"""Deterministic, explainable diagnostics for generated vector artwork."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class InputAssessment:
    """A conservative, deterministic assessment of the uploaded raster."""

    input_kind: str
    level: str
    warning: str | None = None


def build_quality_report(
    *,
    source_rgb: np.ndarray,
    preview_rgb: np.ndarray,
    foreground_mask: np.ndarray,
    path_count: int,
    retained_color_count: int,
    removed_component_count: int,
    svg_paths: list[str],
    model_used: str,
) -> dict[str, Any]:
    """Return a JSON-safe heuristic quality report for one SVG result.

    This is intentionally an output-health heuristic rather than a claim about
    model accuracy.  It combines observable properties of the source, preview,
    and emitted SVG so a caller can show a specific reason when review is
    advisable.  The optional unsupported-input classifier may later replace
    ``input_kind`` and ``level`` with its own deterministic assessment.
    """

    _validate_arrays(source_rgb, preview_rgb, foreground_mask)
    coverage = float(np.count_nonzero(foreground_mask)) / float(foreground_mask.size)
    similarity = _visual_similarity(source_rgb, preview_rgb)
    complexity = _svg_complexity(svg_paths)
    assessment = assess_input_kind(
        source_rgb=source_rgb,
        foreground_coverage=coverage,
        path_count=path_count,
        retained_color_count=retained_color_count,
        svg_complexity=complexity,
    )
    warnings: list[str] = []
    score = 100

    if coverage < 0.002:
        warnings.append(
            "Very little foreground was detected; inspect the SVG for missing artwork."
        )
        score -= 20
    elif coverage > 0.95:
        warnings.append(
            "Foreground covers nearly the full canvas; this may be a photo, document, or dense background."
        )
        score -= 20
    elif coverage > 0.8:
        warnings.append(
            "Foreground covers most of the canvas; review the background mask."
        )
        score -= 10

    if similarity < 0.35:
        warnings.append(
            "The vector preview differs substantially from the source; review before using the SVG."
        )
        score -= 35
    elif similarity < 0.55:
        warnings.append("The vector preview differs noticeably from the source.")
        score -= 20
    elif similarity < 0.72:
        warnings.append(
            "The vector preview has moderate visual differences from the source."
        )
        score -= 8

    if removed_component_count >= 100:
        warnings.append(
            f"{removed_component_count} tiny components were removed as noise."
        )
        score -= 8
    elif removed_component_count > 0:
        warnings.append(
            f"{removed_component_count} tiny component{' was' if removed_component_count == 1 else 's were'} removed as noise."
        )

    if retained_color_count >= 12:
        warnings.append(
            "Many colour layers were retained; the SVG may need manual simplification."
        )
        score -= 5

    if complexity["level"] == "high":
        warnings.append(
            "The SVG contains many drawing commands and may be expensive to edit or render."
        )
        score -= 20
    elif complexity["level"] == "medium":
        warnings.append(
            "The SVG has moderate path complexity; inspect it before production use."
        )
        score -= 5

    if path_count == 0:
        # The worker rejects pathless results before artifact creation. Keeping
        # this branch makes the helper safe for direct pipeline consumers too.
        warnings.append("No editable SVG paths were generated.")
        score = 0

    score = max(0, min(100, score))
    if assessment.warning:
        warnings.insert(0, assessment.warning)
    if assessment.level == "unsupported":
        # Unsupported is an input-fit warning, not an exception: the worker can
        # still complete when it generated legitimate SVG paths for the user to
        # inspect. The score remains useful for sorting outcomes within that set.
        score = min(score, 35)
        level = "unsupported"
    else:
        level = "good" if score >= 75 else "review"
    return {
        "score": score,
        "level": level,
        "warnings": warnings,
        "foreground_coverage": round(coverage, 6),
        "path_count": path_count,
        "retained_color_count": retained_color_count,
        "removed_component_count": removed_component_count,
        "visual_similarity": round(similarity, 6),
        "svg_complexity": complexity,
        "model_used": model_used,
        "input_kind": assessment.input_kind,
    }


def assess_input_kind(
    *,
    source_rgb: np.ndarray,
    foreground_coverage: float,
    path_count: int,
    retained_color_count: int,
    svg_complexity: dict[str, int | str],
) -> InputAssessment:
    """Identify high-confidence unsupported image categories without ML.

    The rules deliberately require several independent signals before marking an
    image unsupported. This prevents a clean flat logo, transparent icon, or
    sparse signature from being rejected merely because it has a few colours or
    sharp edges. Ambiguous inputs remain supported artwork and may still receive
    a lower quality score from the preview/complexity diagnostics.
    """

    sample = _analysis_sample(source_rgb)
    gray = cv2.cvtColor(sample, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(sample, cv2.COLOR_RGB2HSV)
    edge_density = float(np.count_nonzero(cv2.Canny(gray, 80, 160))) / gray.size
    colour_bin_count = _colour_bin_count(sample)
    neutral_ratio = float(np.mean(hsv[:, :, 1] <= 30))
    dark_pixel_ratio = float(np.mean(gray <= 100))
    luma_stddev = float(np.std(gray))
    command_count = int(svg_complexity["command_count"])
    vector_is_dense = path_count > 120 or command_count > 500

    if (
        foreground_coverage >= 0.6
        and colour_bin_count >= 96
        and edge_density >= 0.06
        and luma_stddev >= 35
    ):
        return InputAssessment(
            "photo",
            "unsupported",
            "This image looks photographic; VectorForge is designed for sketches, logos, and flat-colour artwork.",
        )

    if (
        vector_is_dense
        and edge_density >= 0.08
        and neutral_ratio >= 0.72
        and dark_pixel_ratio >= 0.02
    ):
        return InputAssessment(
            "document-or-spreadsheet",
            "unsupported",
            "This image looks like a document or spreadsheet; VectorForge does not reconstruct text or table layouts.",
        )

    if (
        vector_is_dense
        and edge_density >= 0.09
        and colour_bin_count >= 24
        and foreground_coverage >= 0.45
    ):
        return InputAssessment(
            "screenshot-or-interface",
            "unsupported",
            "This image looks like a screenshot or interface; convert the original design asset instead of rasterizing the screen.",
        )

    if retained_color_count <= 1:
        return InputAssessment("line-art", "supported")
    if retained_color_count <= 8:
        return InputAssessment("flat-artwork", "supported")
    return InputAssessment("complex-artwork", "supported")


def _visual_similarity(source_rgb: np.ndarray, preview_rgb: np.ndarray) -> float:
    """Return a reproducible 0--1 preview-fidelity indicator.

    Mean absolute channel difference is deliberately simple and available in
    every supported deployment. It is a comparison indicator, not perceptual
    similarity or a guarantee that an SVG is suitable for a specific use.
    """

    difference = np.abs(source_rgb.astype(np.int16) - preview_rgb.astype(np.int16))
    return float(np.clip(1.0 - difference.mean() / 255.0, 0.0, 1.0))


def _svg_complexity(svg_paths: list[str]) -> dict[str, int | str]:
    command_count = sum(
        path.count("M ") + path.count("L ") + path.count("C ") + path.count(" Z")
        for path in svg_paths
    )
    path_data_characters = sum(len(path) for path in svg_paths)
    if command_count > 1000 or path_data_characters > 100_000:
        level = "high"
    elif command_count > 250 or path_data_characters > 25_000:
        level = "medium"
    else:
        level = "low"
    return {
        "command_count": command_count,
        "path_data_characters": path_data_characters,
        "level": level,
    }


def _analysis_sample(rgb: np.ndarray, longest_side: int = 256) -> np.ndarray:
    """Downscale only for diagnostics so metric cost is bounded and repeatable."""

    height, width = rgb.shape[:2]
    if max(height, width) <= longest_side:
        return rgb
    scale = longest_side / max(height, width)
    return cv2.resize(
        rgb,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )


def _colour_bin_count(rgb: np.ndarray) -> int:
    """Count coarse RGB colour bins, avoiding JPEG pixel-level noise sensitivity."""

    bins = (rgb // 32).reshape(-1, 3)
    return int(np.unique(bins, axis=0).shape[0])


def _validate_arrays(
    source_rgb: np.ndarray, preview_rgb: np.ndarray, foreground_mask: np.ndarray
) -> None:
    if source_rgb.shape != preview_rgb.shape or source_rgb.ndim != 3:
        raise ValueError("source and preview must be RGB arrays with matching shapes")
    if foreground_mask.shape != source_rgb.shape[:2] or foreground_mask.size == 0:
        raise ValueError("foreground mask must match the RGB canvas")
