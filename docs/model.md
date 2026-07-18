# Segmentation model

VectorForge defaults to a deterministic OpenCV foreground mask. When installed,
the optional PyTorch provider uses TorchVision
`DeepLabV3-MobileNetV3-Large` semantic-segmentation weights. Acquisition is an
explicit operator action and is checksum-verified; neither API startup nor
worker inference fetches models over the network.

```bash
cd backend
python scripts/download_segmentation_model.py --destination ../models/deeplabv3_mobilenet_v3_large-fc3c493d.pth
export VECTORFORGE_OPTIONAL_MODEL_PATH=../models/deeplabv3_mobilenet_v3_large-fc3c493d.pth
export VECTORFORGE_SEGMENTATION_MODEL_SHA256=fc3c493d68e89cc31ef488c803d5d7dd2f3190fb570598faa49fef69be8e5e70
```

The downloader intentionally accepts only this pinned public checkpoint. It
does not accept a custom digest to download an arbitrary file; a fine-tuned
checkpoint is always supplied locally. The model is a general semantic
foreground hint, not a trained illustration recognizer. Every completed job
foreground-mask registry ID (`torchvision.deeplabv3-mobilenet-v3-large`),
version (`COCO_WITH_VOC_LABELS_V1`), provider, architecture, and configured
checkpoint SHA-256. If the optional model cannot be used, the job retains the
requested checkpoint identity and records a safe fallback reason before using
OpenCV instead. Operator-provided fine-tuned digests are labelled as
operator-configured rather than as the public TorchVision weight.

The worker accepts only model IDs in the immutable reviewed registry. The
current entry is `torchvision.deeplabv3-mobilenet-v3-large` with version
`COCO_WITH_VOC_LABELS_V1`; an arbitrary URL or architecture cannot be supplied
in a job request. The registry identity is recorded alongside the provider and
digest so later model additions remain auditable.

## Fine-tuning a pretrained checkpoint (later extension)

Fine-tuning starts from the downloaded checkpoint; the command refuses to run
without an existing local base file whose SHA-256 matches the supplied pin.
This prevents an accidental from-scratch run or an unreviewed checkpoint from
being presented as the public TorchVision model.

Expected dataset layout:

```text
<data-dir>/train/images/<stem>.png
<data-dir>/train/masks/<stem>.png
<data-dir>/val/images/<stem>.png
<data-dir>/val/masks/<stem>.png
```

Images may be PNG, JPEG, or WebP. Masks are single-channel binary images where
non-zero pixels are foreground. Keep the dataset outside Git and do not place
user uploads or credentials in the repository.

From `backend/`, after downloading the pinned base checkpoint:

```bash
python scripts/train_segmentation.py \
  --data-dir <dataset> \
  --base-checkpoint ../models/deeplabv3_mobilenet_v3_large-fc3c493d.pth \
  --output ../models/vectorforge-finetuned.pth
```

The command loads the local pretrained state dictionary, trains the existing
21-class architecture with class `1` as foreground, evaluates every epoch on
the held-out `val` split, and saves the best checkpoint with validation Dice,
architecture, and base-checkpoint digest metadata. Record the dataset
provenance, validation result, output digest, and applicable third-party terms
before deployment. A validation metric is evidence for review, not a claim of
general accuracy; evaluate on representative artwork before enabling the
checkpoint.

To use a reviewed fine-tuned file, copy it into the ignored `models/` directory
and set both environment variables to its path and exact SHA-256 digest:

```bash
export VECTORFORGE_OPTIONAL_MODEL_PATH=../models/vectorforge-finetuned.pth
export VECTORFORGE_SEGMENTATION_MODEL_SHA256=<fine-tuned-file-sha256>
```

The OpenCV fallback remains the dependable default whenever the file is
missing, the digest does not match, TorchVision is unavailable, or inference
cannot run on the configured device.

TorchVision is BSD-3-Clause; pretrained-weight terms must also be reviewed
before redistribution. See the upstream [TorchVision model
documentation](https://docs.pytorch.org/vision/master/models.html) and
[license](https://github.com/pytorch/vision/blob/main/LICENSE).
