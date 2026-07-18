"""Optional local ML providers used by the vectorization worker.

Nothing in this package downloads weights.  Model acquisition is an explicit
operator action performed by :mod:`scripts.download_segmentation_model`.
"""

from .manifest import DEEPLABV3_MOBILENET_V3_LARGE
from .segmentation import (
    ModelAvailability,
    ModelSelection,
    TorchVisionDeepLabProvider,
    select_configured_segmentation_model,
)

__all__ = [
    "DEEPLABV3_MOBILENET_V3_LARGE",
    "ModelAvailability",
    "ModelSelection",
    "TorchVisionDeepLabProvider",
    "select_configured_segmentation_model",
]
