# API

- `POST /api/v1/vectorizations` submits multipart `image`, `mode`, `color_count`, `smoothing`, `min_component_area`, and `use_segmentation_model`; it returns `202` with the job ID, queued status, and artifact route URLs. Clients should send a unique `Idempotency-Key` header for each intended conversion. Replaying the same source/options with the same key returns the original job; a different request with that key returns `409`.
- `GET /api/v1/vectorizations/{id}` returns queued, processing, completed, or failed state, settings, dimensions, model/fallback metadata, safe error details, a completed-job `quality` report, and completed artifact URLs.
- `GET /api/v1/vectorizations/{id}/artifacts/{original|svg|preview|comparison}` downloads an artifact once available.
- `GET /healthz`, `GET /readyz`, and `GET /metrics` provide local operational status.

The service accepts PNG, JPEG, and WebP only, with configurable byte/pixel limits. Invalid files return a typed 4xx response; worker failures expose a safe error message rather than implementation details.

`quality` is nullable for queued, processing, failed, and historical jobs. See
[quality-report documentation](quality.md) for field definitions and correct
interpretation.
