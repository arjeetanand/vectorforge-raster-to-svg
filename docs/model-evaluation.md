# Foreground-model evaluation

VectorForge keeps OpenCV as the dependable foreground-mask default and treats
TorchVision segmentation as an optional, explicitly provisioned enhancement.
The repository includes a reproducible comparison command so a model can be
reviewed against the fallback before it is enabled for a deployment.

## Run the comparison

From the repository root, compare the supplied fixtures without loading a
model:

```bash
# From the repository root, use the project Python environment.
PYTHONPATH=backend .venv/bin/python backend/scripts/evaluate_segmentation.py
```

To compare a locally downloaded, checksum-verified checkpoint with OpenCV:

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/evaluate_segmentation.py \
  --model-path models/deeplabv3_mobilenet_v3_large-fc3c493d.pth \
  --expected-sha256 fc3c493d68e89cc31ef488c803d5d7dd2f3190fb570598faa49fef69be8e5e70 \
  --output /tmp/vectorforge-segmentation.json
```

Weights are never downloaded by this command. Provision them first using the
explicit downloader described in [model.md](model.md). A focused run can list
one or more files with `--fixture path/to/image.png`; otherwise the command
recursively scans `samples/`. Use `--format markdown` for a compact review
table.

## What the report means

The report is intentionally labelled `model-vs-opencv-mask-agreement`. For
each decodable fixture it records dimensions, foreground coverage, the
production mask source, and (when the model is available) these deterministic
pairwise indicators:

- `iou`: intersection over union of the two binary masks;
- `dice`: overlap between the two masks;
- `disagreement_ratio`: proportion of pixels with different labels;
- `foreground_coverage_delta`: absolute difference in foreground proportions.

These are not precision, recall, or segmentation accuracy. The repository
fixtures do not include hand-labelled foreground masks, so no quality claim
can be made from this report alone. A model should only be promoted after a
representative held-out image/mask dataset is evaluated with ground-truth
metrics and the checkpoint provenance is recorded.

Transparent fixtures are reported with `production_source: alpha`, even when
the command also computes model-vs-OpenCV agreement. This mirrors runtime
precedence: meaningful alpha wins, then the optional model, then OpenCV.
Malformed, unsupported, oversized, or over-pixel fixtures are listed as
`skipped` with a safe decoder reason; one bad fixture does not abort the rest
of the report.

## Reproducibility and review checklist

1. Keep the fixture set fixed and record its provenance in
   [fixtures.md](fixtures.md).
2. Run with the same processing limits as the worker (10 MB, 16 MP, longest
   side 2048 px) unless a deliberate experiment documents the override.
3. Record the model architecture, checkpoint digest, device, command, and
   report output outside the source repository when a checkpoint is not meant
   to be committed.
4. Treat disagreement as a review signal. It does not establish that either
   mask is correct.
5. For fine-tuned checkpoints, require held-out validation metrics before
   setting `VECTORFORGE_OPTIONAL_MODEL_PATH` in a deployment.
