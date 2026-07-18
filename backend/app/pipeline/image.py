"""Safe raster decoding and orientation normalisation."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

SUPPORTED_FORMATS = frozenset({"PNG", "JPEG", "WEBP"})


class ImageDecodeError(ValueError):
    """Raised for malformed, unsupported, or oversized raster payloads."""


@dataclass(frozen=True)
class DecodedImage:
    rgb: np.ndarray
    alpha: np.ndarray | None
    format: str
    original_width: int
    original_height: int

    @property
    def width(self) -> int:
        return int(self.rgb.shape[1])

    @property
    def height(self) -> int:
        return int(self.rgb.shape[0])


def decode_image(
    data: bytes,
    *,
    max_bytes: int = 10 * 1024 * 1024,
    max_pixels: int = 16_000_000,
    processing_longest_side: int = 2048,
) -> DecodedImage:
    """Decode a supported payload, honour EXIF, and bound processing size.

    MIME headers are intentionally not trusted; Pillow identifies and decodes
    the bytes themselves.  The returned RGB array is contiguous uint8.
    """

    if not data:
        raise ImageDecodeError("image payload is empty")
    if len(data) > max_bytes:
        raise ImageDecodeError("image payload exceeds the 10 MB limit")
    try:
        with Image.open(BytesIO(data)) as opened:
            image_format = opened.format
            if image_format not in SUPPORTED_FORMATS:
                raise ImageDecodeError("only PNG, JPEG, and WebP images are supported")
            opened.verify()
        with Image.open(BytesIO(data)) as opened:
            original_width, original_height = opened.size
            if original_width * original_height > max_pixels:
                raise ImageDecodeError("image exceeds the 16 megapixel limit")
            image = ImageOps.exif_transpose(opened)
            if max(image.size) > processing_longest_side:
                scale = processing_longest_side / max(image.size)
                target = (
                    max(1, round(image.width * scale)),
                    max(1, round(image.height * scale)),
                )
                image = image.resize(target, Image.Resampling.LANCZOS)
            alpha = None
            if "A" in image.getbands():
                alpha = np.ascontiguousarray(
                    np.asarray(image.getchannel("A"), dtype=np.uint8)
                )
            rgb = np.ascontiguousarray(np.asarray(image.convert("RGB"), dtype=np.uint8))
    except ImageDecodeError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ImageDecodeError("image content could not be decoded") from exc
    return DecodedImage(rgb, alpha, image_format, original_width, original_height)
