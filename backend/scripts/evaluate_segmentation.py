#!/usr/bin/env python3
"""Compare the optional segmentation model with the OpenCV mask.

This command is deliberately an agreement report, not an accuracy benchmark:
the repository fixtures do not contain hand-labelled foreground masks.  It is
safe to run without a checkpoint and never attempts to download one.  When a
local checkpoint is supplied, each fixture is decoded using the same limits as
the worker and the model mask is compared with the deterministic OpenCV mask.

Examples (from the repository root)::

    python backend/scripts/evaluate_segmentation.py
    python backend/scripts/evaluate_segmentation.py \
        --model-path models/deeplabv3_mobilenet_v3_large-fc3c493d.pth \
        --output /tmp/vectorforge-segmentation.json

Run ``python backend/scripts/evaluate_segmentation.py --help`` for all
options.  Model weights must have been provisioned explicitly beforehand.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

# Allow the documented ``python backend/scripts/...`` form from the repository
# root as well as ``python scripts/...`` from the backend directory.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ml.segmentation import (  # noqa: E402
    ModelSelection,
    select_configured_segmentation_model,
)
from app.ml.manifest import get_model_artifact  # noqa: E402
from app.pipeline.image import ImageDecodeError, decode_image  # noqa: E402
from app.pipeline.segmentation import opencv_foreground_mask  # noqa: E402

DEFAULT_FIXTURES = Path(__file__).resolve().parents[2] / "samples"
SUPPORTED_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})
MaskProvider = Callable[[np.ndarray], np.ndarray]


def compare_masks(opencv_mask: np.ndarray, model_mask: np.ndarray) -> dict[str, float]:
    """Return deterministic mask-agreement indicators.

    These metrics compare two foreground hypotheses only.  Without annotated
    ground truth they must not be described as precision, recall, or accuracy.
    """

    if opencv_mask.shape != model_mask.shape:
        raise ValueError("mask dimensions do not match")
    classical = np.asarray(opencv_mask) > 0
    predicted = np.asarray(model_mask) > 0
    intersection = int(np.count_nonzero(classical & predicted))
    union = int(np.count_nonzero(classical | predicted))
    classical_count = int(np.count_nonzero(classical))
    predicted_count = int(np.count_nonzero(predicted))
    total = int(classical.size)
    equal = int(np.count_nonzero(classical == predicted))
    iou = 1.0 if union == 0 else intersection / union
    dice_denominator = classical_count + predicted_count
    dice = 1.0 if dice_denominator == 0 else 2 * intersection / dice_denominator
    return {
        "iou": round(iou, 6),
        "dice": round(dice, 6),
        "disagreement_ratio": round(1 - equal / total, 6),
        "foreground_coverage_delta": round(
            abs(classical_count - predicted_count) / total, 6
        ),
    }


def _fixture_paths(root: Path, explicit: list[Path] | None) -> list[Path]:
    paths = explicit or [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    return sorted(paths, key=lambda path: path.name.lower())


def _safe_fixture_name(path: Path) -> str:
    """Keep reports portable and free of local absolute paths."""

    return path.name


def _coverage(mask: np.ndarray) -> float:
    return round(float(np.count_nonzero(mask)) / float(mask.size), 6)


def _model_status(selection: ModelSelection, requested: bool) -> dict[str, Any]:
    if not requested:
        return {"status": "not-requested", "reason": "model-not-requested"}
    status: dict[str, Any] = {
        "status": "unavailable",
        "reason": selection.fallback_reason or "model-unavailable",
        "model_id": selection.model_id,
    }
    try:
        artifact = get_model_artifact(selection.model_id)
    except ValueError:
        artifact = None
    if artifact is not None:
        status.update(
            {
                "architecture": artifact.architecture,
                "checkpoint": artifact.name,
                "checkpoint_sha256": artifact.sha256,
            }
        )
    if selection.model is None:
        return status
    status["status"] = "ready"
    status["reason"] = None
    return status


def build_report(
    paths: Iterable[Path],
    *,
    model_provider: MaskProvider | None = None,
    model_status: dict[str, Any] | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    max_pixels: int = 16_000_000,
    processing_longest_side: int = 2048,
) -> dict[str, Any]:
    """Build a JSON-safe report for raster fixture paths.

    ``model_provider`` is injectable so tests can use a deterministic stub and
    never need TorchVision or downloaded weights.  Production callers should
    pass the provider returned by :func:`select_configured_segmentation_model`.
    """

    if model_status is None:
        model_status = (
            {"status": "ready", "reason": None}
            if model_provider is not None
            else {"status": "not-requested", "reason": "model-not-requested"}
        )
    status = dict(model_status)
    fixtures: list[dict[str, Any]] = []
    provider = model_provider
    for path in paths:
        fixture: dict[str, Any] = {"name": _safe_fixture_name(path)}
        try:
            decoded = decode_image(
                path.read_bytes(),
                max_bytes=max_bytes,
                max_pixels=max_pixels,
                processing_longest_side=processing_longest_side,
            )
        except (OSError, ImageDecodeError) as exc:
            fixture.update({"status": "skipped", "reason": str(exc)})
            fixtures.append(fixture)
            continue

        classical_mask = opencv_foreground_mask(decoded.rgb)
        meaningful_alpha = decoded.alpha is not None and np.any(decoded.alpha < 255)
        fixture.update(
            {
                "status": "ok",
                "format": decoded.format,
                "dimensions": {"width": decoded.width, "height": decoded.height},
                "original_dimensions": {
                    "width": decoded.original_width,
                    "height": decoded.original_height,
                },
                "meaningful_alpha": bool(meaningful_alpha),
                "opencv": {"foreground_coverage": _coverage(classical_mask)},
            }
        )

        model_mask: np.ndarray | None = None
        if provider is not None and status.get("status") == "ready":
            try:
                model_mask = np.asarray(provider(decoded.rgb))
                if model_mask.shape != classical_mask.shape:
                    raise ValueError("mask dimensions do not match")
            except Exception:
                # Persist only a stable reason, never a raw model traceback or
                # local checkpoint path.  The next fixtures should not retry a
                # provider that already failed in this process.
                provider = None
                status = {"status": "unavailable", "reason": "model-inference-failed"}

        if model_mask is None:
            fixture["model"] = {
                "status": status.get("status", "unavailable"),
                "reason": status.get("reason"),
            }
            fixture["production_source"] = "alpha" if meaningful_alpha else "opencv"
        else:
            fixture["model"] = {
                "status": "ok",
                "foreground_coverage": _coverage(model_mask),
            }
            fixture["agreement"] = compare_masks(classical_mask, model_mask)
            fixture["production_source"] = (
                "alpha" if meaningful_alpha else "torchvision"
            )
        fixtures.append(fixture)

    compared = [fixture["agreement"] for fixture in fixtures if "agreement" in fixture]
    summary: dict[str, Any] = {
        "fixture_count": len(fixtures),
        "ok_count": sum(fixture["status"] == "ok" for fixture in fixtures),
        "skipped_count": sum(fixture["status"] == "skipped" for fixture in fixtures),
        "compared_count": len(compared),
        "model_status": status,
    }
    if compared:
        for key in (
            "iou",
            "dice",
            "disagreement_ratio",
            "foreground_coverage_delta",
        ):
            summary[f"mean_{key}"] = round(
                sum(float(metrics[key]) for metrics in compared) / len(compared),
                6,
            )
    return {
        "schema_version": "vectorforge.segmentation-comparison.v1",
        "comparison": "model-vs-opencv-mask-agreement",
        "accuracy_claim": False,
        "note": (
            "Agreement metrics compare foreground hypotheses; annotated masks "
            "are required before reporting segmentation accuracy."
        ),
        "summary": summary,
        "fixtures": fixtures,
    }


def _markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# VectorForge segmentation comparison",
        "",
        "This is a model-vs-OpenCV mask-agreement report, not an accuracy benchmark.",
        "",
        f"- Fixtures: {summary['fixture_count']} ({summary['compared_count']} compared)",
        f"- Model status: {summary['model_status']['status']}",
        "",
        "| Fixture | Status | Production mask | IoU | Dice | Disagreement |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for fixture in report["fixtures"]:
        agreement = fixture.get("agreement", {})
        lines.append(
            "| {name} | {status} | {source} | {iou} | {dice} | {disagreement} |".format(
                name=fixture["name"],
                status=fixture["status"],
                source=fixture.get("production_source", "-"),
                iou=agreement.get("iou", "-"),
                dice=agreement.get("dice", "-"),
                disagreement=agreement.get("disagreement_ratio", "-"),
            )
        )
    return "\n".join(lines) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=DEFAULT_FIXTURES,
        help="directory searched recursively when --fixture is not supplied",
    )
    parser.add_argument(
        "--fixture",
        action="append",
        type=Path,
        help="specific fixture path; repeat for a focused comparison",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        help="local checkpoint path; no model is loaded when omitted",
    )
    parser.add_argument(
        "--expected-sha256", help="full SHA-256 pin for the local checkpoint"
    )
    parser.add_argument("--device", default="cpu", help="Torch device (default: cpu)")
    parser.add_argument(
        "--output",
        type=Path,
        help="optional report destination; stdout is always written",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="stdout/output report format (default: json)",
    )
    parser.add_argument("--max-bytes", type=int, default=10 * 1024 * 1024)
    parser.add_argument("--max-pixels", type=int, default=16_000_000)
    parser.add_argument("--processing-longest-side", type=int, default=2048)
    args = parser.parse_args()
    if args.max_bytes < 1 or args.max_pixels < 1 or args.processing_longest_side < 1:
        parser.error("image limits must be positive")
    return args


def main() -> int:
    args = _parse_args()
    paths = _fixture_paths(args.fixtures, args.fixture)
    if not paths:
        print("No supported raster fixtures were found.", file=sys.stderr)
        return 2

    selection = ModelSelection(None, "model-not-requested")
    if args.model_path is not None:
        selection = select_configured_segmentation_model(
            True,
            args.model_path,
            device=args.device,
            expected_sha256=args.expected_sha256,
        )
    status = _model_status(selection, args.model_path is not None)
    report = build_report(
        paths,
        model_provider=selection.model,
        model_status=status,
        max_bytes=args.max_bytes,
        max_pixels=args.max_pixels,
        processing_longest_side=args.processing_longest_side,
    )
    rendered = (
        json.dumps(report, indent=2, sort_keys=True)
        if args.format == "json"
        else _markdown_report(report)
    )
    print(rendered, end="" if rendered.endswith("\n") else "\n")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
