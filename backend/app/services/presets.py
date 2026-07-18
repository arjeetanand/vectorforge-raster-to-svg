"""Named conversion presets shared by batch and single-image clients.

Presets are deliberately plain data.  They are not a second vectorization
algorithm; each expands to the same validated :class:`VectorizationOptions`
used by the normal API.  Keeping them here prevents frontend/worker defaults
from drifting.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


PRESETS: dict[str, dict[str, Any]] = {
    "signature-line-art": {
        "label": "Signature / line art",
        "description": "Single-ink marks, signatures, and clean sketches.",
        "options": {
            "mode": "line-art",
            "color_count": 2,
            "smoothing": 0.35,
            "min_component_area": 18,
            "use_segmentation_model": False,
        },
    },
    "flat-color-logo": {
        "label": "Flat-color logo",
        "description": "Brand marks with a small number of solid colors.",
        "options": {
            "mode": "illustration",
            "color_count": 6,
            "smoothing": 0.25,
            "min_component_area": 24,
            "use_segmentation_model": False,
        },
    },
    "transparent-icon": {
        "label": "Transparent icon",
        "description": "Icons with meaningful alpha transparency.",
        "options": {
            "mode": "illustration",
            "color_count": 8,
            "smoothing": 0.30,
            "min_component_area": 20,
            "use_segmentation_model": False,
        },
    },
    "print-ready-artwork": {
        "label": "Print-ready artwork",
        "description": "Flat illustrations where preserving color layers matters.",
        "options": {
            "mode": "illustration",
            "color_count": 12,
            "smoothing": 0.20,
            "min_component_area": 40,
            "use_segmentation_model": False,
        },
    },
}


def list_presets() -> list[dict[str, Any]]:
    """Return stable, JSON-safe preset descriptors for an API response."""

    return [
        {
            "id": key,
            "label": value["label"],
            "description": value["description"],
            "options": deepcopy(value["options"]),
        }
        for key, value in PRESETS.items()
    ]


def preset_options(preset_id: str) -> dict[str, Any]:
    """Expand a preset or raise a safe ``KeyError`` for unknown IDs."""

    try:
        return deepcopy(PRESETS[preset_id]["options"])
    except KeyError as exc:
        raise KeyError(f"Unknown conversion preset: {preset_id}") from exc
