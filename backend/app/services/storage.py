from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import Settings, get_settings

ALLOWED_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
ARTIFACT_NAMES = {
    "original": ("source", None),
    "svg": ("vector.svg", "image/svg+xml"),
    "preview": ("preview.png", "image/png"),
    "comparison": ("comparison.png", "image/png"),
}


def _invalid_upload(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message
    )


async def persist_upload(
    upload: UploadFile, job_id: str, settings: Settings | None = None
) -> dict:
    """Validate decoded pixels and store the unmodified source below its UUID directory."""
    settings = settings or get_settings()
    raw = await upload.read(settings.max_upload_bytes + 1)
    if not raw:
        raise _invalid_upload("The upload is empty.")
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Uploads are limited to 10 MB.")
    try:
        from io import BytesIO

        with Image.open(BytesIO(raw)) as checked:
            image_format = checked.format
            checked.verify()
        with Image.open(BytesIO(raw)) as image:
            normalized = ImageOps.exif_transpose(image)
            width, height = normalized.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise _invalid_upload(
            "Upload must be a valid PNG, JPEG, or WebP image."
        ) from exc
    if image_format not in ALLOWED_FORMATS:
        raise _invalid_upload("Only PNG, JPEG, and WebP images are supported.")
    if width * height > settings.max_image_pixels:
        raise HTTPException(
            status_code=413, detail="Images are limited to 16 megapixels."
        )

    artifact_dir = settings.artifact_root / job_id
    artifact_dir.mkdir(parents=True, exist_ok=False)
    suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[image_format]
    source_path = artifact_dir / f"source{suffix}"
    source_path.write_bytes(raw)
    return {
        "artifact_dir": str(artifact_dir),
        "filename": Path(upload.filename or "upload").name[:255],
        "mime_type": ALLOWED_FORMATS[image_format],
        "sha256": hashlib.sha256(raw).hexdigest(),
        "width": width,
        "height": height,
    }


def source_path(artifact_dir: str | Path) -> Path:
    matches = sorted(Path(artifact_dir).glob("source.*"))
    if len(matches) != 1:
        raise FileNotFoundError("Expected exactly one original image artifact.")
    return matches[0]


def artifact_path(artifact_dir: str | Path, name: str) -> tuple[Path, str | None]:
    if name not in ARTIFACT_NAMES:
        raise KeyError(name)
    filename, content_type = ARTIFACT_NAMES[name]
    if name == "original":
        path = source_path(artifact_dir)
    else:
        path = Path(artifact_dir) / filename
    return path, content_type


def cleanup_expired_artifacts(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    root = settings.artifact_root
    if not root.exists():
        return 0
    cutoff = datetime.now(UTC) - timedelta(hours=settings.artifact_ttl_hours)
    removed = 0
    for child in root.iterdir():
        if not child.is_dir():
            continue
        modified = datetime.fromtimestamp(child.stat().st_mtime, UTC)
        if modified < cutoff:
            shutil.rmtree(child)
            removed += 1
    return removed
