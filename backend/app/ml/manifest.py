"""Pinned provenance for the optional TorchVision segmentation checkpoint."""

from __future__ import annotations

from dataclasses import dataclass


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


DEEPLABV3_MOBILENET_V3_LARGE = ModelArtifact(
    name="DeepLabV3-MobileNetV3-Large COCO_WITH_VOC_LABELS_V1",
    architecture="deeplabv3_mobilenet_v3_large",
    url="https://download.pytorch.org/models/deeplabv3_mobilenet_v3_large-fc3c493d.pth",
    filename="deeplabv3_mobilenet_v3_large-fc3c493d.pth",
    sha256="fc3c493d68e89cc31ef488c803d5d7dd2f3190fb570598faa49fef69be8e5e70",
)
