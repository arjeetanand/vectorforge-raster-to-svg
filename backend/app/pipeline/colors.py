"""Colour quantization and connected-component noise filtering."""

from __future__ import annotations

import cv2
import numpy as np


def quantize_rgb(
    rgb: np.ndarray, colors: int, mask: np.ndarray | None = None
) -> np.ndarray:
    """Quantize RGB deterministically using OpenCV k-means."""

    if not 2 <= colors <= 16:
        raise ValueError("colors must be between 2 and 16")
    h, w = rgb.shape[:2]
    pixels = rgb.reshape(-1, 3)
    active = np.ones(len(pixels), dtype=bool) if mask is None else mask.reshape(-1) > 0
    samples = pixels[active]
    if len(samples) == 0:
        return rgb.copy()
    k = min(colors, len(np.unique(samples, axis=0)))
    if k == 1:
        out = rgb.copy()
        out.reshape(-1, 3)[active] = samples[0]
        return out
    cv2.setRNGSeed(7)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 25, 0.5)
    _, labels, centers = cv2.kmeans(
        samples.astype(np.float32), k, None, criteria, 3, cv2.KMEANS_PP_CENTERS
    )
    out = rgb.copy().reshape(-1, 3)
    out[active] = np.uint8(np.clip(centers[labels.ravel()], 0, 255))
    return out.reshape(h, w, 3)


def filter_components(mask: np.ndarray, min_area: int) -> np.ndarray:
    """Remove connected foreground components smaller than ``min_area``."""

    if min_area < 1:
        raise ValueError("min_area must be positive")
    binary = (mask > 0).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    filtered = np.zeros_like(binary)
    for label in range(1, count):
        if stats[label, cv2.CC_STAT_AREA] >= min_area:
            filtered[labels == label] = 255
    return filtered
