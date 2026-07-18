"""Optional local ML providers used by the vectorization worker.

Nothing in this package downloads weights.  Model acquisition is an explicit
operator action performed by :mod:`scripts.download_segmentation_model`.
"""

from .manifest import (
    DEFAULT_SEGMENTATION_MODEL_ID,
    DEEPLABV3_MOBILENET_V3_LARGE,
    SEGMENTATION_MODEL_REGISTRY,
    ModelArtifact,
    get_model_artifact,
    registered_model_ids,
)
from .segmentation import (
    ModelAvailability,
    ModelSelection,
    TorchVisionDeepLabProvider,
    select_configured_segmentation_model,
)

__all__ = [
    "DEEPLABV3_MOBILENET_V3_LARGE",
    "DEFAULT_SEGMENTATION_MODEL_ID",
    "SEGMENTATION_MODEL_REGISTRY",
    "ModelArtifact",
    "get_model_artifact",
    "registered_model_ids",
    "ModelAvailability",
    "ModelSelection",
    "TorchVisionDeepLabProvider",
    "select_configured_segmentation_model",
]
