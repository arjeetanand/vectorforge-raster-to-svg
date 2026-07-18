from __future__ import annotations

from io import BytesIO
from xml.etree import ElementTree

import cv2
import numpy as np
import pytest
from PIL import Image

from app.pipeline.colors import filter_components, quantize_rgb
from app.pipeline.contours import contour_to_svg_path
from app.pipeline.image import ImageDecodeError, decode_image
from app.pipeline.segmentation import foreground_mask
from app.pipeline.types import VectorizationOptions
from app.pipeline.vectorize import vectorize_image
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
    source.putpixel((15, 10), (0, 0, 0))
    source_path = tmp_path / "input.png"
    source_path.write_bytes(png_bytes(source))
    output = vectorize_image(
        source_path, tmp_path / "artifacts", {"mode": "line-art", "smoothing": 0}
    )
    assert output.svg_path.name == "vector.svg"
    assert output.preview_path.is_file()
    assert output.comparison_path.is_file()
    assert Image.open(output.comparison_path).size == (62, 20)
