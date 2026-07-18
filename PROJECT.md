# VectorForge project guide

## Purpose

VectorForge converts supported raster artwork into editable SVG paths. It is for
signatures, scanned marks, logos, icons, and flat-colour illustrations. It is
**not** a photo-vectorization, OCR, spreadsheet, or document-reconstruction
product.

## Product contract

Every completed job must produce an editable SVG and corresponding preview and
comparison images. A result must be explainable: the API and UI expose the
processing mode, foreground-mask source, fallback reason where applicable, and
a quality report. Inputs that look unsupported must be warned about or rejected
with a safe, actionable message; they must never be presented as a trustworthy
SVG merely because a preview exists.

## Architecture

`frontend/` is a React + Vite TypeScript workbench. It submits uploads to
`backend/`, polls job state, renders the actual SVG artifact, and allows a user
to download outputs.

`backend/` is a FastAPI API plus Celery worker. The API validates and stores an
upload, records a PostgreSQL job, and sends its ID through Redis. The worker
runs deterministic OpenCV preprocessing and vectorization, optionally using a
locally installed TorchVision DeepLabV3-MobileNetV3-Large foreground model.
Artifacts live in UUID-scoped directories under the configured data root.

## Processing precedence

1. Transparent alpha is foreground when meaningful alpha exists.
2. A requested, installed, checksum-verified pretrained model may provide a
   foreground mask.
3. OpenCV classical masking is the dependable fallback.

The system never downloads model weights during an API request or worker
inference. It does not train a model from scratch. Fine-tuning is only a later
option for a user-provided image/mask dataset.

## Current implementation priorities

Phase 1 is reliability:

- Quality scoring and safe unsupported-input detection
- Output diagnostics: paths, colours, filtered components, similarity, model
  provenance, and warnings
- Idempotent submission and retry-safe workers
- Deterministic fixture and regression tests
- Clear user documentation and safe errors

Do not add batch ZIPs, webhooks, SDKs, Figma/Adobe integrations, cloud hosting,
authentication, billing, or enterprise deployment work unless the user asks.

## Quality rules

- Quality score is an explainable heuristic, not a model-accuracy claim.
- Visual similarity must compare the generated preview with the source and be
  presented as an indicator, never as a guarantee.
- A completed job must have at least one SVG path and all three output artifacts.
- Do not reject a supported flat logo simply for using a small number of colours
  or for having an alpha channel.
- Avoid storing raw exception messages, credentials, or source image bytes in
  metadata or logs.

## Validation

Run backend tests and static checks from the documented virtual environment and
frontend `lint`, `test`, and `build` checks. Docker Compose is the supported
full-stack runtime. Each material code/configuration/test/docs change and each
real error must be appended to `LEARNINGS.md` with date, workstream, cause,
resolution, verification, and prevention.
