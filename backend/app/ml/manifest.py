"""Pinned provenance for the optional TorchVision segmentation checkpoint."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class ModelArtifact:
    """A model file accepted by the explicit downloader.

    ``sha256`` is the complete digest verified by both the explicit downloader
    and the provider's first local load.  Deployments using a fine-tuned
    checkpoint replace it through ``VECTORFORGE_SEGMENTATION_MODEL_SHA256``.
    """

    name: str
    architecture: str
    url: str
    filename: str
    sha256: str
    # Stable registry identity and provenance.  These values are deliberately
    # separate from ``name`` so future checkpoints can be added without
    # changing the metadata contract or relying on a mutable file path.
    model_id: str = ""
    version: str = ""
    provider: str = "torchvision"
    provenance_url: str | None = None


DEEPLABV3_MOBILENET_V3_LARGE = ModelArtifact(
    name="DeepLabV3-MobileNetV3-Large COCO_WITH_VOC_LABELS_V1",
    architecture="deeplabv3_mobilenet_v3_large",
    url="https://download.pytorch.org/models/deeplabv3_mobilenet_v3_large-fc3c493d.pth",
    filename="deeplabv3_mobilenet_v3_large-fc3c493d.pth",
    sha256="fc3c493d68e89cc31ef488c803d5d7dd2f3190fb570598faa49fef69be8e5e70",
    model_id="torchvision.deeplabv3-mobilenet-v3-large",
    version="COCO_WITH_VOC_LABELS_V1",
    provider="torchvision",
    provenance_url="https://docs.pytorch.org/vision/master/models.html",
)


# The registry is intentionally static and immutable.  Adding a model means
# adding a reviewed manifest entry, not allowing a request to supply an
# arbitrary URL or architecture.  Inference still requires an operator to
# provision the matching local checkpoint explicitly.
SEGMENTATION_MODEL_REGISTRY: Mapping[str, ModelArtifact] = MappingProxyType(
    {DEEPLABV3_MOBILENET_V3_LARGE.model_id: DEEPLABV3_MOBILENET_V3_LARGE}
)
DEFAULT_SEGMENTATION_MODEL_ID = DEEPLABV3_MOBILENET_V3_LARGE.model_id


def registered_model_ids() -> tuple[str, ...]:
    """Return deterministic IDs that may be selected by the worker."""

    return tuple(SEGMENTATION_MODEL_REGISTRY)


def get_model_artifact(model_id: str = DEFAULT_SEGMENTATION_MODEL_ID) -> ModelArtifact:
    """Look up a reviewed model manifest without touching the network."""

    try:
        return SEGMENTATION_MODEL_REGISTRY[model_id]
    except KeyError as exc:
        raise ValueError(f"Unknown segmentation model: {model_id}") from exc


def is_valid_sha256(value: str) -> bool:
    """Return whether ``value`` is a normalized, full SHA-256 digest."""

    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )
