"""Foreground extraction with deterministic classical fallbacks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class MaskResult:
    mask: np.ndarray
    source: str


SegmentationModel = Callable[[np.ndarray], np.ndarray]


def foreground_mask(
    rgb: np.ndarray,
    alpha: np.ndarray | None = None,
    model: SegmentationModel | None = None,
) -> MaskResult:
    """Return a binary foreground mask using alpha, an optional model, or CV.

    Fully opaque alpha is not semantic foreground information, so it falls
    through to a model/fallback. Model failures deliberately fail soft so a
    missing optional weight cannot make the conversion service unavailable.
    """

    _require_rgb(rgb)
    if alpha is not None and alpha.shape == rgb.shape[:2] and np.any(alpha < 255):
        return MaskResult(_clean_mask((alpha > 0).astype(np.uint8) * 255), "alpha")
    if model is not None:
        try:
            predicted = np.asarray(model(rgb))
            if predicted.shape != rgb.shape[:2]:
                raise ValueError("segmentation mask dimensions do not match image")
            return MaskResult(
                _clean_mask((predicted > 0).astype(np.uint8) * 255), "torchvision"
            )
        except Exception:
            # The model is optional. The job metadata should report fallback.
            pass
    return MaskResult(opencv_foreground_mask(rgb), "opencv")


def opencv_foreground_mask(rgb: np.ndarray) -> np.ndarray:
    """Infer foreground against the most likely border/background colour."""

    _require_rgb(rgb)
    h, w = rgb.shape[:2]
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    border = np.concatenate((lab[0], lab[-1], lab[:, 0], lab[:, -1]), axis=0)
    background = np.median(border, axis=0)
    distance = np.linalg.norm(lab - background, axis=2)
    # Otsu adapts to both dark-on-light sketches and flat coloured logos.
    scaled = cv2.normalize(distance, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, by_distance = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    border_luma = np.median(
        np.concatenate((gray[0], gray[-1], gray[:, 0], gray[:, -1]))
    )
    threshold_type = cv2.THRESH_BINARY_INV if border_luma >= 128 else cv2.THRESH_BINARY
    _, by_luminance = cv2.threshold(gray, 0, 255, threshold_type + cv2.THRESH_OTSU)
    # A distance mask catches colourful marks; luminance catches black ink.
    mask = cv2.bitwise_or(by_distance, by_luminance)
    if h >= 3 and w >= 3:
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return _clean_mask(mask)


def _clean_mask(mask: np.ndarray) -> np.ndarray:
    mask = (mask > 0).astype(np.uint8) * 255
    if mask.size == 0:
        return mask
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    # Preserve meaningful tiny details; only reject isolated one-pixel decoder noise.
    out = np.zeros_like(mask)
    for label in range(1, count):
        if stats[label, cv2.CC_STAT_AREA] >= 2:
            out[labels == label] = 255
    return out


def _require_rgb(rgb: np.ndarray) -> None:
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
        raise ValueError("rgb must be a uint8 HxWx3 array")
