# Segmentation model

VectorForge defaults to a deterministic OpenCV foreground mask. When installed, the optional PyTorch provider uses TorchVision `DeepLabV3-MobileNetV3-Large` semantic-segmentation weights. Download is explicit and checksum-verified; inference never fetches models over the network.

```bash
cd backend
python scripts/download_segmentation_model.py --destination ../models/deeplabv3_mobilenet_v3_large-fc3c493d.pth
export VECTORFORGE_OPTIONAL_MODEL_PATH=../models/deeplabv3_mobilenet_v3_large-fc3c493d.pth
export VECTORFORGE_SEGMENTATION_MODEL_SHA256=fc3c493d68e89cc31ef488c803d5d7dd2f3190fb570598faa49fef69be8e5e70
```

The model is a general semantic foreground hint, not a trained illustration recognizer. `python scripts/train_segmentation.py --data-dir <dataset> --output <checkpoint>` fine-tunes the 21-class architecture with foreground masks encoded as class 1 and reports validation Dice. Preserve model provenance and applicable third-party terms when distributing weights.
