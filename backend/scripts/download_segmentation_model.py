#!/usr/bin/env python3
"""Explicitly download and checksum-verify the optional DeepLab checkpoint.

Run from ``backend/``.  It is intentionally separate from application startup
and worker inference, so an unavailable network can never affect a conversion
job.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

# Allow the documented ``python scripts/download_segmentation_model.py`` form
# from any working directory; app imports remain local and never trigger a
# package installation or network activity.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ml.manifest import DEEPLABV3_MOBILENET_V3_LARGE


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as model_file:
        for block in iter(lambda: model_file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(destination: Path, expected_sha256: str | None = None) -> Path:
    """Download once, verify SHA-256, then atomically publish the file."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    expected = (expected_sha256 or DEEPLABV3_MOBILENET_V3_LARGE.sha256).lower()
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        raise ValueError("expected SHA-256 must be a 64-character digest")
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".model-", delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            with urllib.request.urlopen(DEEPLABV3_MOBILENET_V3_LARGE.url, timeout=60) as response:
                while chunk := response.read(1024 * 1024):
                    temporary.write(chunk)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        temporary.flush()
        os.fsync(temporary.fileno())
    try:
        actual = sha256_file(temporary_path)
        if actual != expected:
            raise ValueError("downloaded checkpoint SHA-256 did not match the configured digest")
        temporary_path.replace(destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True, help="local checkpoint path")
    parser.add_argument(
        "--expected-sha256",
        help="optional full SHA-256 pin for a reviewed fine-tuned checkpoint",
    )
    args = parser.parse_args()
    try:
        saved = download(args.destination, args.expected_sha256)
    except Exception as exc:
        print(f"Model download failed: {exc}", file=sys.stderr)
        return 1
    print(f"Verified model written to {saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
