# API

- `POST /api/v1/vectorizations` submits multipart `image`, `mode`, `color_count`, `smoothing`, `min_component_area`, and `use_segmentation_model`; it returns `202` with the job ID, queued status, and artifact route URLs. Clients should send a unique `Idempotency-Key` header for each intended conversion. Replaying the same source/options with the same key returns the original job; a different request with that key returns `409`.
- `GET /api/v1/vectorizations/{id}` returns queued, processing, completed, or failed state, settings, dimensions, model/fallback metadata, safe error details, a completed-job `quality` report, and completed artifact URLs.
- `GET /api/v1/vectorizations/{id}/artifacts/{original|svg|preview|comparison}` downloads an artifact once available.
- `POST /api/v1/vectorization-batches` accepts repeated `images` fields or one
  ZIP `archive`, returns `202` with a batch ID and per-file jobs, and supports
  the same vectorization options plus `Idempotency-Key`.
- `GET /api/v1/vectorization-batches/{id}` polls aggregate and per-file status.
- `POST /api/v1/vectorization-batches/{id}/retry-failed` requeues only failed
  files.
- After a batch reaches a terminal state, download
  `artifacts/results.zip`, `artifacts/report.csv`, or `artifacts/report.json`.
- `GET /api/v1/presets` returns the reviewed signature, logo, transparent-icon,
  and print-ready option presets.
- `GET /healthz`, `GET /readyz`, and `GET /metrics` provide local operational status.

The service accepts PNG, JPEG, and WebP only, with configurable byte/pixel limits. Invalid files return a typed 4xx response; worker failures expose a safe error message rather than implementation details.

`quality` is nullable for queued, processing, failed, and historical jobs. See
[quality-report documentation](quality.md) for field definitions and correct
interpretation.

Batch uploads are limited to 100 files or a 50 MB ZIP. Each contained image is
still subject to the normal 10 MB, decode, and pixel limits. Archive paths are
sanitized and never extracted outside UUID-scoped artifact directories.

When `quality.model_metadata` is present, `model_id` and `version` identify the
reviewed registry entry, while `checkpoint_sha256` identifies the exact local
file used. Operator-configured fine-tuned checkpoints are labelled as local
operator checkpoints rather than being presented as the public TorchVision
weight. These fields are provenance metadata; they do not claim segmentation
accuracy.
