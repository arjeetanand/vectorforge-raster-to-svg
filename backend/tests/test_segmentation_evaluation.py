from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from scripts.evaluate_segmentation import build_report, compare_masks


def test_compare_masks_reports_agreement_indicators_without_accuracy_labels() -> None:
    classical = np.array([[255, 0], [0, 0]], dtype=np.uint8)
    model = np.array([[255, 0], [0, 255]], dtype=np.uint8)

    metrics = compare_masks(classical, model)

    assert metrics == {
        "iou": 0.5,
        "dice": 0.666667,
        "disagreement_ratio": 0.25,
        "foreground_coverage_delta": 0.25,
    }


def test_build_report_compares_injected_model_and_respects_alpha_precedence(
    tmp_path: Path,
) -> None:
    opaque = Image.new("RGB", (12, 8), "white")
    opaque.paste((0, 0, 0), (2, 2, 10, 6))
    opaque_path = tmp_path / "opaque.png"
    opaque.save(opaque_path)

    transparent = Image.new("RGBA", (12, 8), (255, 255, 255, 0))
    transparent.paste((0, 0, 255, 255), (3, 1, 9, 7))
    transparent_path = tmp_path / "transparent.png"
    transparent.save(transparent_path)

    # A provider stub keeps this test deterministic and does not import or
    # download TorchVision weights.
    def all_foreground(rgb: np.ndarray) -> np.ndarray:
        return np.full(rgb.shape[:2], 255, dtype=np.uint8)

    report = build_report(
        [opaque_path, transparent_path],
        model_provider=all_foreground,
        model_status={"status": "ready", "reason": None},
    )

    assert report["accuracy_claim"] is False
    assert report["summary"]["fixture_count"] == 2
    assert report["summary"]["compared_count"] == 2
    by_name = {fixture["name"]: fixture for fixture in report["fixtures"]}
    assert by_name["opaque.png"]["production_source"] == "torchvision"
    assert by_name["transparent.png"]["meaningful_alpha"] is True
    assert by_name["transparent.png"]["production_source"] == "alpha"
    assert by_name["opaque.png"]["agreement"]["iou"] < 1


def test_build_report_records_decode_failures_without_exposing_paths(
    tmp_path: Path,
) -> None:
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not an image")

    report = build_report([broken])

    fixture = report["fixtures"][0]
    assert fixture == {
        "name": "broken.png",
        "status": "skipped",
        "reason": "image content could not be decoded",
    }


def test_build_report_stops_retrying_after_model_failure(tmp_path: Path) -> None:
    paths: list[Path] = []
    for name in ("a.png", "b.png"):
        image_path = tmp_path / name
        Image.new("RGB", (8, 8), "white").save(image_path)
        paths.append(image_path)
    calls = 0

    def failing_provider(_rgb: np.ndarray) -> np.ndarray:
        nonlocal calls
        calls += 1
        raise RuntimeError("test-only model failure")

    report = build_report(
        paths,
        model_provider=failing_provider,
        model_status={"status": "ready", "reason": None},
    )

    assert calls == 1
    assert report["summary"]["model_status"] == {
        "status": "unavailable",
        "reason": "model-inference-failed",
    }
    assert all("agreement" not in fixture for fixture in report["fixtures"])
