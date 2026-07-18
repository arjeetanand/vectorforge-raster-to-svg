from __future__ import annotations

from pathlib import Path
from importlib import import_module

import numpy as np
import pytest

from app.ml.manifest import (
    DEFAULT_SEGMENTATION_MODEL_ID,
    DEEPLABV3_MOBILENET_V3_LARGE,
    get_model_artifact,
    registered_model_ids,
)
from app.ml.segmentation import (
    TorchVisionDeepLabProvider,
    select_configured_segmentation_model,
)
from app.pipeline.vectorize import vectorize_image
from app.pipeline.vectorize import _model_metadata


def test_manifest_uses_a_full_torchvision_sha256_pin() -> None:
    artifact = DEEPLABV3_MOBILENET_V3_LARGE
    assert artifact.filename.endswith(".pth")
    assert artifact.url.endswith(artifact.filename)
    assert len(artifact.sha256) == 64
    assert int(artifact.sha256, 16) >= 0


def test_registry_exposes_only_reviewed_local_model_manifests() -> None:
    assert registered_model_ids() == (DEFAULT_SEGMENTATION_MODEL_ID,)
    artifact = get_model_artifact(DEFAULT_SEGMENTATION_MODEL_ID)
    assert artifact.model_id == DEFAULT_SEGMENTATION_MODEL_ID
    assert artifact.version == "COCO_WITH_VOC_LABELS_V1"
    assert artifact.provider == "torchvision"
    with pytest.raises(ValueError, match="Unknown segmentation model"):
        get_model_artifact("operator-supplied-url")


def test_model_selection_never_enables_a_missing_checkpoint(tmp_path: Path) -> None:
    selected = select_configured_segmentation_model(True, tmp_path / "missing.pth")
    assert selected.model is None
    assert selected.fallback_reason == "model-unavailable"
    assert selected.model_id == DEFAULT_SEGMENTATION_MODEL_ID


def test_model_selection_rejects_unregistered_model_without_io(
    tmp_path: Path,
) -> None:
    selected = select_configured_segmentation_model(
        True,
        tmp_path / "anything.pth",
        model_id="operator-supplied-url",
    )
    assert selected.model is None
    assert selected.fallback_reason == "model-not-registered"


def test_provider_validates_input_before_loading_weights(tmp_path: Path) -> None:
    provider = TorchVisionDeepLabProvider(tmp_path / "missing.pth")
    assert provider.expected_sha256 == DEEPLABV3_MOBILENET_V3_LARGE.sha256
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
    source = Image.new("RGB", (20, 20), "white")
    source.paste((0, 0, 0), (5, 5, 15, 15))
    source.save(source_path)
    output = vectorize_image(
        source_path,
        tmp_path / "output",
        {"mode": "line-art", "use_segmentation_model": True},
    )
    assert output.model_used == "opencv-fallback:model-not-configured"
    assert output.quality["model_metadata"] == {
        "requested": True,
        "provider": "opencv",
        "model_id": DEFAULT_SEGMENTATION_MODEL_ID,
        "version": "COCO_WITH_VOC_LABELS_V1",
        "architecture": "deeplabv3_mobilenet_v3_large",
        "checkpoint": "DeepLabV3-MobileNetV3-Large COCO_WITH_VOC_LABELS_V1",
        "checkpoint_sha256": DEEPLABV3_MOBILENET_V3_LARGE.sha256,
        "fallback_reason": "model-not-configured",
    }


def test_torchvision_provenance_uses_the_pinned_checkpoint() -> None:
    metadata = _model_metadata(
        requested=True,
        model_used="torchvision",
        fallback_reason=None,
        expected_sha256=None,
    )
    assert metadata["provider"] == "torchvision"
    assert metadata["model_id"] == DEFAULT_SEGMENTATION_MODEL_ID
    assert metadata["version"] == "COCO_WITH_VOC_LABELS_V1"
    assert metadata["architecture"] == "deeplabv3_mobilenet_v3_large"
    assert metadata["checkpoint_sha256"] == DEEPLABV3_MOBILENET_V3_LARGE.sha256
    assert metadata["fallback_reason"] is None


def test_custom_checkpoint_provenance_is_not_labelled_as_public_weight() -> None:
    metadata = _model_metadata(
        requested=True,
        model_used="torchvision",
        fallback_reason=None,
        expected_sha256="a" * 64,
    )
    assert metadata["version"] == "operator-configured"
    assert metadata["checkpoint"] == "operator-configured local checkpoint"
    assert metadata["checkpoint_sha256"] == "a" * 64
