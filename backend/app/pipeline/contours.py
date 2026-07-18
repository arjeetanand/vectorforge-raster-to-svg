"""Contour approximation and path geometry helpers."""

from __future__ import annotations

import cv2
import numpy as np


def simplify_contour(contour: np.ndarray, *, smoothing: float) -> np.ndarray:
    """Douglas--Peucker simplify a closed OpenCV contour deterministically."""

    if not 0 <= smoothing <= 1:
        raise ValueError("smoothing must be between 0 and 1")
    perimeter = cv2.arcLength(contour, True)
    # Keep small marks legible while smoothing large scanned shapes.
    epsilon = perimeter * (0.001 + smoothing * 0.012)
    simplified = cv2.approxPolyDP(contour, epsilon, True)
    return simplified.reshape(-1, 2).astype(float)


def contour_to_svg_path(points: np.ndarray, *, smoothing: float) -> str:
    """Serialize a closed polygon with optional Catmull--Rom Bézier segments."""

    if len(points) < 3:
        return ""
    points = np.asarray(points, dtype=float)
    start = _point(points[0])
    if smoothing <= 0 or len(points) < 4:
        return (
            "M "
            + start
            + " "
            + " ".join("L " + _point(point) for point in points[1:])
            + " Z"
        )
    tension = smoothing / 6.0
    segments = ["M " + start]
    size = len(points)
    for index in range(size):
        previous = points[(index - 1) % size]
        current = points[index]
        following = points[(index + 1) % size]
        after_following = points[(index + 2) % size]
        control_1 = current + (following - previous) * tension
        control_2 = following - (after_following - current) * tension
        segments.append(
            "C " + _point(control_1) + " " + _point(control_2) + " " + _point(following)
        )
    return " ".join(segments) + " Z"


def _point(point: np.ndarray) -> str:
    return f"{point[0]:.2f} {point[1]:.2f}"
