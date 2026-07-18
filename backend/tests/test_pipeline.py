from __future__ import annotations

from io import BytesIO
import json
from xml.etree import ElementTree

import cv2
import numpy as np
import pytest
from PIL import Image

from app.pipeline.colors import filter_components, quantize_rgb
from app.pipeline.quality import build_quality_report
from app.pipeline.contours import contour_to_svg_path
from app.pipeline.image import ImageDecodeError, decode_image
from app.pipeline.segmentation import foreground_mask
from app.pipeline.types import VectorizationOptions
from app.pipeline.vectorize import NoVectorPathsError, vectorize_image
from app.pipeline.vectorizer import vectorize


def png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_decode_preserves_transparency_and_resizes() -> None:
    image = Image.new("RGBA", (100, 50), (255, 255, 255, 0))
    image.putpixel((20, 20), (10, 20, 30, 255))
    decoded = decode_image(png_bytes(image), processing_longest_side=40)
    assert decoded.format == "PNG"
    assert decoded.original_width == 100
    assert (decoded.width, decoded.height) == (40, 20)
    assert decoded.alpha is not None
    assert decoded.alpha.shape == (20, 40)


@pytest.mark.parametrize("payload", [b"", b"not-an-image"])
def test_decode_rejects_invalid_content(payload: bytes) -> None:
    with pytest.raises(ImageDecodeError):
        decode_image(payload)


def test_alpha_takes_precedence_over_model() -> None:
    rgb = np.full((10, 10, 3), 255, dtype=np.uint8)
    alpha = np.zeros((10, 10), dtype=np.uint8)
    alpha[2:8, 2:8] = 255
    result = foreground_mask(rgb, alpha, lambda _: np.zeros((10, 10), dtype=np.uint8))
    assert result.source == "alpha"
    assert result.mask[4, 4] == 255
    assert result.mask[0, 0] == 0


def test_unavailable_model_uses_opencv_fallback() -> None:
    rgb = np.full((50, 50, 3), 255, dtype=np.uint8)
    rgb[15:35, 15:35] = (0, 0, 0)
    result = foreground_mask(
        rgb, model=lambda _: (_ for _ in ()).throw(RuntimeError("weights unavailable"))
    )
    assert result.source == "opencv"
    assert result.mask[25, 25] == 255


def test_quantization_is_deterministic_and_component_filtering_removes_noise() -> None:
    rgb = np.zeros((20, 20, 3), dtype=np.uint8)
    rgb[:, :10] = (240, 20, 20)
    rgb[:, 10:] = (20, 20, 240)
    assert np.array_equal(quantize_rgb(rgb, 2), quantize_rgb(rgb, 2))
    mask = np.zeros((20, 20), dtype=np.uint8)
    mask[1, 1] = 255
    mask[10:15, 10:15] = 255
    filtered = filter_components(mask, 4)
    assert filtered[1, 1] == 0
    assert filtered[12, 12] == 255


def test_quality_report_is_json_safe_and_explains_removed_noise() -> None:
    source = np.full((20, 20, 3), 255, dtype=np.uint8)
    source[5:15, 5:15] = (0, 0, 0)
    mask = np.zeros((20, 20), dtype=np.uint8)
    mask[5:15, 5:15] = 255
    report = build_quality_report(
        source_rgb=source,
        preview_rgb=source.copy(),
        foreground_mask=mask,
        path_count=1,
        retained_color_count=1,
        removed_component_count=2,
        svg_paths=["M 5.00 5.00 L 15.00 5.00 L 15.00 15.00 Z"],
        model_used="opencv",
    )
    assert report["score"] == 100
    assert report["level"] == "good"
    assert report["foreground_coverage"] == 0.25
    assert report["visual_similarity"] == 1.0
    assert report["removed_component_count"] == 2
    assert report["svg_complexity"]["command_count"] == 4
    assert report["model_used"] == "opencv"
    assert report["input_kind"] == "line-art"
    assert any("2 tiny components" in warning for warning in report["warnings"])
    json.dumps(report)


def test_quality_report_marks_low_similarity_or_complex_svg_for_review() -> None:
    source = np.zeros((20, 20, 3), dtype=np.uint8)
    preview = np.full((20, 20, 3), 255, dtype=np.uint8)
    mask = np.full((20, 20), 255, dtype=np.uint8)
    dense_path = "M 0.00 0.00 " + " ".join("L 1.00 1.00" for _ in range(1001)) + " Z"
    report = build_quality_report(
        source_rgb=source,
        preview_rgb=preview,
        foreground_mask=mask,
        path_count=1,
        retained_color_count=1,
        removed_component_count=0,
        svg_paths=[dense_path],
        model_used="opencv",
    )
    assert report["level"] == "review"
    assert report["score"] < 75
    assert report["visual_similarity"] == 0.0
    assert report["svg_complexity"]["level"] == "high"
    assert any("substantially" in warning for warning in report["warnings"])


def test_quality_report_marks_photo_like_input_as_unsupported() -> None:
    rng = np.random.default_rng(7)
    source = rng.integers(0, 256, size=(80, 80, 3), dtype=np.uint8)
    report = build_quality_report(
        source_rgb=source,
        preview_rgb=source.copy(),
        foreground_mask=np.full((80, 80), 255, dtype=np.uint8),
        path_count=20,
        retained_color_count=6,
        removed_component_count=0,
        svg_paths=["M 0.00 0.00 L 1.00 1.00 Z"],
        model_used="opencv",
    )
    assert report["level"] == "unsupported"
    assert report["input_kind"] == "photo"
    assert any("photographic" in warning for warning in report["warnings"])


def test_quality_report_marks_dense_neutral_document_as_unsupported() -> None:
    source = np.full((200, 200, 3), 255, dtype=np.uint8)
    for coordinate in range(10, 200, 10):
        cv2.line(source, (coordinate, 0), (coordinate, 199), (35, 35, 35), 1)
        cv2.line(source, (0, coordinate), (199, coordinate), (35, 35, 35), 1)
    report = build_quality_report(
        source_rgb=source,
        preview_rgb=source.copy(),
        foreground_mask=np.full((200, 200), 255, dtype=np.uint8),
        path_count=200,
        retained_color_count=2,
        removed_component_count=0,
        svg_paths=["M 0.00 0.00 " + " ".join("L 1.00 1.00" for _ in range(501))],
        model_used="opencv",
    )
    assert report["level"] == "unsupported"
    assert report["input_kind"] == "document-or-spreadsheet"
    assert any("document or spreadsheet" in warning for warning in report["warnings"])


def test_bezier_path_is_closed_and_uses_cubics_when_enabled() -> None:
    points = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=float)
    path = contour_to_svg_path(points, smoothing=0.5)
    assert path.startswith("M 0.00 0.00")
    assert " C " in path
    assert path.endswith(" Z")


def test_line_art_generates_valid_svg_fill_paths() -> None:
    rgb = np.full((100, 100, 3), 255, dtype=np.uint8)
    cv2.rectangle(rgb, (20, 20), (80, 80), (0, 0, 0), thickness=-1)
    result = vectorize(
        rgb, VectorizationOptions(mode="line-art", smoothing=0, min_component_area=10)
    )
    root = ElementTree.fromstring(result.svg)
    assert root.attrib["viewBox"] == "0 0 100 100"
    assert result.path_count == 1
    assert 'fill="#111827"' in result.svg


def test_illustration_keeps_hole_with_evenodd_svg_rule() -> None:
    rgb = np.full((100, 100, 3), 255, dtype=np.uint8)
    cv2.circle(rgb, (50, 50), 35, (255, 0, 0), thickness=-1)
    cv2.circle(rgb, (50, 50), 12, (255, 255, 255), thickness=-1)
    result = vectorize(
        rgb,
        VectorizationOptions(
            mode="illustration", colors=2, smoothing=0, min_component_area=10
        ),
    )
    ElementTree.fromstring(result.svg)
    assert 'fill-rule="evenodd"' in result.svg
    assert result.path_count >= 1


def test_worker_facade_writes_named_artifacts(tmp_path) -> None:
    source = Image.new("RGB", (30, 20), "white")
    # A single pixel is deliberately filtered as noise by the production
    # minimum-component threshold; use a clear supported line-art mark here.
    source.paste((0, 0, 0), (10, 6, 20, 16))
    source_path = tmp_path / "input.png"
    source_path.write_bytes(png_bytes(source))
    output = vectorize_image(
        source_path, tmp_path / "artifacts", {"mode": "line-art", "smoothing": 0}
    )
    assert output.svg_path.name == "vector.svg"
    assert output.preview_path.is_file()
    assert output.comparison_path.is_file()
    assert Image.open(output.comparison_path).size == (62, 20)
    assert output.quality["path_count"] >= 1
    assert output.quality["model_used"] == output.model_used


def test_worker_facade_rejects_an_empty_vector_result(tmp_path) -> None:
    source_path = tmp_path / "blank.png"
    source_path.write_bytes(png_bytes(Image.new("RGB", (30, 20), "white")))
    with pytest.raises(NoVectorPathsError, match="No editable vector paths"):
        vectorize_image(source_path, tmp_path / "artifacts", {"mode": "illustration"})
