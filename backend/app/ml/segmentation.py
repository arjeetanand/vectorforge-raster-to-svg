"""Local-only TorchVision DeepLab foreground-mask provider.

The provider deliberately has no calls to TorchVision's weight enum or model
hub: both can initiate a network download when weights are missing.  A caller
must point it to a locally provisioned checkpoint instead.
"""

from __future__ import annotations

import importlib.util
import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from .manifest import (
    DEFAULT_SEGMENTATION_MODEL_ID,
    DEEPLABV3_MOBILENET_V3_LARGE,
    ModelArtifact,
    get_model_artifact,
    is_valid_sha256,
)


class SegmentationModelUnavailable(RuntimeError):
    """Raised when the optional model cannot be used without network access."""


@dataclass(frozen=True)
class ModelAvailability:
    available: bool
    reason: str | None = None
    model_id: str = DEFAULT_SEGMENTATION_MODEL_ID


@dataclass(frozen=True)
class ModelSelection:
    """The callable selected for one job and a safe metadata fallback reason."""

    model: "TorchVisionDeepLabProvider | None"
    fallback_reason: str | None = None
    model_id: str = DEFAULT_SEGMENTATION_MODEL_ID


class TorchVisionDeepLabProvider:
    """Run local DeepLabV3-MobileNetV3-Large weights as a foreground masker."""

    def __init__(
        self,
        weights_path: Path,
        *,
        device: str = "cpu",
        expected_sha256: str | None = None,
        artifact: ModelArtifact = DEEPLABV3_MOBILENET_V3_LARGE,
    ) -> None:
        self.weights_path = Path(weights_path)
        self.device = device
        self.artifact = artifact
        # Direct provider construction is pinned too; callers may only
        # override this with an explicitly reviewed full digest.
        self.expected_sha256 = (expected_sha256 or artifact.sha256).lower()
        self._model: Any | None = None
        self._torch: Any | None = None

    def availability(self) -> ModelAvailability:
        """Check prerequisites without loading a model or doing I/O over HTTP."""

        if not self.weights_path.is_file():
            return ModelAvailability(False, "model-unavailable", self.artifact.model_id)
        if self.expected_sha256 is not None and not is_valid_sha256(
            self.expected_sha256
        ):
            return ModelAvailability(
                False, "model-checksum-invalid", self.artifact.model_id
            )
        if (
            importlib.util.find_spec("torch") is None
            or importlib.util.find_spec("torchvision") is None
        ):
            return ModelAvailability(
                False, "torchvision-unavailable", self.artifact.model_id
            )
        return ModelAvailability(True, model_id=self.artifact.model_id)

    def __call__(self, rgb: np.ndarray) -> np.ndarray:
        return self.predict(rgb)

    def predict(self, rgb: np.ndarray) -> np.ndarray:
        """Return a uint8 foreground mask (all non-background VOC classes)."""

        _require_rgb(rgb)
        model, torch = self._load()
        tensor = (
            torch.from_numpy(np.ascontiguousarray(rgb))
            .permute(2, 0, 1)
            .to(dtype=torch.float32)
        )
        tensor = tensor.div(255.0)
        mean = torch.tensor((0.485, 0.456, 0.406), device=tensor.device).view(3, 1, 1)
        std = torch.tensor((0.229, 0.224, 0.225), device=tensor.device).view(3, 1, 1)
        tensor = ((tensor - mean) / std).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            logits = model(tensor)["out"]
            classes = logits.argmax(dim=1)[0]
        # VOC class zero is background; all other predicted classes are artwork.
        return classes.ne(0).to(dtype=torch.uint8).cpu().numpy() * 255

    def _load(self) -> tuple[Any, Any]:
        if self._model is not None and self._torch is not None:
            return self._model, self._torch
        status = self.availability()
        if not status.available:
            raise SegmentationModelUnavailable(status.reason or "model-unavailable")
        try:
            import torch
            from torchvision.models.segmentation import deeplabv3_mobilenet_v3_large

            if self.artifact.architecture != DEEPLABV3_MOBILENET_V3_LARGE.architecture:
                raise SegmentationModelUnavailable("model-architecture-unsupported")

            if self.device.startswith("cuda") and not torch.cuda.is_available():
                raise SegmentationModelUnavailable(
                    "requested CUDA device is unavailable"
                )
            if (
                self.expected_sha256 is not None
                and _sha256_file(self.weights_path) != self.expected_sha256
            ):
                raise SegmentationModelUnavailable(
                    "model checksum did not match configured pin"
                )
            # ``weights=None`` and ``weights_backbone=None`` are essential: no
            # implicit model/backbone download is allowed in worker inference.
            model = deeplabv3_mobilenet_v3_large(
                weights=None, weights_backbone=None, num_classes=21
            )
            try:
                checkpoint = torch.load(
                    self.weights_path, map_location=self.device, weights_only=True
                )
            except TypeError:  # Older supported Torch versions lack weights_only.
                checkpoint = torch.load(self.weights_path, map_location=self.device)
            state_dict = (
                checkpoint.get("state_dict", checkpoint)
                if isinstance(checkpoint, dict)
                else checkpoint
            )
            model.load_state_dict(state_dict)
            model.to(self.device)
            model.eval()
        except SegmentationModelUnavailable:
            raise
        except Exception as exc:
            raise SegmentationModelUnavailable(
                "local model could not be loaded"
            ) from exc
        self._model, self._torch = model, torch
        return model, torch


@lru_cache(maxsize=4)
def _cached_provider(
    path: str,
    device: str,
    expected_sha256: str | None,
    model_id: str,
) -> TorchVisionDeepLabProvider:
    return TorchVisionDeepLabProvider(
        Path(path),
        device=device,
        expected_sha256=expected_sha256,
        artifact=get_model_artifact(model_id),
    )


def select_configured_segmentation_model(
    enabled: bool,
    weights_path: Path | None,
    *,
    device: str = "cpu",
    expected_sha256: str | None = None,
    model_id: str = DEFAULT_SEGMENTATION_MODEL_ID,
) -> ModelSelection:
    """Select an optional provider, never attempting model acquisition.

    The returned reason is intentionally compact and safe for persisted job
    metadata.  It gives users a useful explanation without paths or internals.
    """

    if not enabled:
        return ModelSelection(None, model_id=model_id)
    try:
        artifact = get_model_artifact(model_id)
    except ValueError:
        return ModelSelection(None, "model-not-registered", model_id)
    if weights_path is None:
        return ModelSelection(None, "model-not-configured", model_id)
    # An operator can override this pin for a reviewed fine-tuned checkpoint.
    # Otherwise the public TorchVision checkpoint always has a full SHA-256.
    expected_sha256 = expected_sha256 or artifact.sha256
    provider = _cached_provider(str(weights_path), device, expected_sha256, model_id)
    availability = provider.availability()
    if not availability.available:
        return ModelSelection(None, availability.reason, model_id)
    return ModelSelection(provider, model_id=model_id)


def _require_rgb(rgb: np.ndarray) -> None:
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
        raise ValueError("rgb must be a uint8 HxWx3 array")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as checkpoint:
        for block in iter(lambda: checkpoint.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
