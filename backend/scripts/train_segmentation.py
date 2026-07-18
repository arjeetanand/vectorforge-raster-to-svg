#!/usr/bin/env python3
"""Fine-tune the local foreground model on paired image and mask folders.

Expected layout::

  <data-dir>/train/images/<stem>.png
  <data-dir>/train/masks/<stem>.png
  <data-dir>/val/images/<stem>.png
  <data-dir>/val/masks/<stem>.png

Masks are binary: non-zero pixels are foreground. The resulting checkpoint
keeps TorchVision's 21 output classes and trains class 1 as foreground, so it
can be loaded by VectorForge's optional local provider without conversion.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path


def _pairs(root: Path) -> list[tuple[Path, Path]]:
    images = root / "images"
    masks = root / "masks"
    supported = {".png", ".jpg", ".jpeg", ".webp"}
    pairs = [(image, masks / f"{image.stem}.png") for image in images.iterdir() if image.suffix.lower() in supported]
    return [(image, mask) for image, mask in pairs if mask.is_file()]


def _batch(pairs: list[tuple[Path, Path]], size: int, device: str):
    import torch
    from PIL import Image, ImageOps

    images, targets = [], []
    for image_path, mask_path in pairs:
        image = ImageOps.exif_transpose(Image.open(image_path).convert("RGB")).resize((size, size))
        mask = Image.open(mask_path).convert("L").resize((size, size), Image.Resampling.NEAREST)
        image_tensor = torch.from_numpy(__import__("numpy").asarray(image).copy()).permute(2, 0, 1).float().div(255)
        image_tensor = (image_tensor - torch.tensor((0.485, 0.456, 0.406)).view(3, 1, 1)) / torch.tensor((0.229, 0.224, 0.225)).view(3, 1, 1)
        images.append(image_tensor)
        targets.append((torch.from_numpy(__import__("numpy").asarray(mask).copy()) > 0).long())
    return torch.stack(images).to(device), torch.stack(targets).to(device)


def _dice(prediction, target) -> float:
    foreground = prediction.eq(1)
    target = target.bool()
    intersection = (foreground & target).sum().item()
    total = foreground.sum().item() + target.sum().item()
    return (2 * intersection + 1) / (total + 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.size < 32:
        parser.error("epochs, batch size, and image size must be positive (size >= 32)")

    import torch
    from torchvision.models.segmentation import deeplabv3_mobilenet_v3_large

    train_pairs, val_pairs = _pairs(args.data_dir / "train"), _pairs(args.data_dir / "val")
    if not train_pairs or not val_pairs:
        parser.error("both train and val folders need matching images/<stem> and masks/<stem>.png pairs")
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        parser.error("CUDA was requested but is unavailable")
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    model = deeplabv3_mobilenet_v3_large(weights=None, weights_backbone=None, num_classes=21).to(args.device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    criterion = torch.nn.CrossEntropyLoss()
    best_dice = -1.0
    args.output.parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, args.epochs + 1):
        model.train()
        random.shuffle(train_pairs)
        for offset in range(0, len(train_pairs), args.batch_size):
            images, targets = _batch(train_pairs[offset : offset + args.batch_size], args.size, args.device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images)["out"], targets)
            loss.backward()
            optimizer.step()
        model.eval()
        scores: list[float] = []
        with torch.inference_mode():
            for offset in range(0, len(val_pairs), args.batch_size):
                images, targets = _batch(val_pairs[offset : offset + args.batch_size], args.size, args.device)
                scores.append(_dice(model(images)["out"].argmax(dim=1), targets))
        dice = sum(scores) / len(scores)
        print(f"epoch={epoch} validation_dice={dice:.4f}")
        if dice > best_dice:
            best_dice = dice
            torch.save({"state_dict": model.state_dict(), "validation_dice": dice, "input_size": args.size}, args.output)
    print(f"best_validation_dice={best_dice:.4f} checkpoint={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
