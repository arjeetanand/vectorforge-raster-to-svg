# Segmentation model

VectorForge defaults to a deterministic OpenCV foreground mask. When installed, the optional PyTorch provider uses TorchVision `DeepLabV3-MobileNetV3-Large` semantic-segmentation weights. Download is explicit and checksum-verified; inference never fetches models over the network.

```bash
cd backend
python scripts/download_segmentation_model.py --destination ../models/deeplabv3_mobilenet_v3_large-fc3c493d.pth
export VECTORFORGE_OPTIONAL_MODEL_PATH=../models/deeplabv3_mobilenet_v3_large-fc3c493d.pth
export VECTORFORGE_SEGMENTATION_MODEL_SHA256=fc3c493d68e89cc31ef488c803d5d7dd2f3190fb570598faa49fef69be8e5e70
```

The model is a general semantic foreground hint, not a trained illustration recognizer. Every completed job stores the provider used and, when the TorchVision model is active, its architecture and pinned checkpoint SHA-256. If the optional model cannot be used, the job records the safe fallback reason and uses OpenCV instead.

`python scripts/train_segmentation.py --data-dir <dataset> --output <checkpoint>` fine-tunes this pretrained 21-class architecture with foreground masks encoded as class 1 and reports validation Dice. It does not train a model from scratch. Only use a fine-tuned checkpoint after evaluating it on a representative held-out dataset; record its source dataset, validation Dice, digest, and applicable third-party terms before deployment.
