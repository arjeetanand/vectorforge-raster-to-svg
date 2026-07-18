from __future__ import annotations

from pathlib import Path
from importlib import import_module

import numpy as np
import pytest

from app.ml.manifest import DEEPLABV3_MOBILENET_V3_LARGE
from app.ml.segmentation import (
    TorchVisionDeepLabProvider,
    select_configured_segmentation_model,
)
from app.pipeline.vectorize import vectorize_image


def test_manifest_uses_a_full_torchvision_sha256_pin() -> None:
    artifact = DEEPLABV3_MOBILENET_V3_LARGE
    assert artifact.filename.endswith(".pth")
    assert artifact.url.endswith(artifact.filename)
    assert len(artifact.sha256) == 64
    assert int(artifact.sha256, 16) >= 0


def test_model_selection_never_enables_a_missing_checkpoint(tmp_path: Path) -> None:
    selected = select_configured_segmentation_model(True, tmp_path / "missing.pth")
    assert selected.model is None
    assert selected.fallback_reason == "model-unavailable"


def test_provider_validates_input_before_loading_weights(tmp_path: Path) -> None:
    provider = TorchVisionDeepLabProvider(tmp_path / "missing.pth")
    with pytest.raises(ValueError, match="uint8 HxWx3"):
        provider.predict(np.zeros((4, 4), dtype=np.uint8))


def test_requested_model_without_config_reports_worker_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PIL import Image

    worker_facade = import_module("app.pipeline.vectorize")
    monkeypatch.setattr(
        worker_facade,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "optional_model_path": None,
                "segmentation_model_device": "cpu",
                "segmentation_model_sha256": None,
                "max_upload_bytes": 10 * 1024 * 1024,
                "max_image_pixels": 16_000_000,
                "max_processing_dimension": 2048,
            },
        )(),
    )
    source_path = tmp_path / "source.png"
    Image.new("RGB", (20, 20), "white").save(source_path)
    output = vectorize_image(
        source_path,
        tmp_path / "output",
        {"mode": "line-art", "use_segmentation_model": True},
    )
    assert output.model_used == "opencv-fallback:model-not-configured"
