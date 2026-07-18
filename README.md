# VectorForge — Raster artwork to editable SVG

VectorForge is a local, asynchronous computer-vision application that converts
supported raster artwork into editable SVG paths. It is designed for signatures,
sketches, logos, transparent icons, and flat-colour illustrations—not
photographs or document reconstruction.

The product promise is deliberately practical: produce a usable SVG, explain
how it was produced, and warn you when the input or output needs review.

## Who it is for

- Marketing and design teams preparing reusable brand assets
- Branding, print, signage, and e-commerce asset workflows
- Developers who need a local raster-to-SVG REST API
- Anyone cleaning up simple scanned marks or flat artwork

## What happens to an image

1. The API validates the file by content and decodes it safely (including EXIF
   orientation), enforcing a 10 MB and 16-megapixel limit.
2. The image is resized to at most 2048 px on its longest side and stored in a
   UUID-scoped temporary artifact directory.
3. The worker chooses a foreground mask using this precedence:
   transparent alpha → optional checksum-verified TorchVision model → OpenCV
   fallback.
4. OpenCV denoises the mask, removes components below the configured area, and
   either thresholds line art or quantizes flat colours.
5. Contours and holes are found, simplified with Douglas–Peucker, optionally
   smoothed with Catmull–Rom-to-cubic Bézier segments, and serialized as
   escaped filled SVG paths with a correct `viewBox`.
6. The worker writes SVG, preview, comparison, and source artifacts and stores
   quality/model diagnostics in PostgreSQL. The browser polls until the job is
   `completed` or `failed`.

The output is filled geometry. VectorForge does not infer semantic layers,
centerline strokes, fonts, OCR text, or a photograph's objects.

## Architecture

```text
React/Vite workbench → FastAPI → PostgreSQL job metadata
                              ↘ Redis → Celery worker → OpenCV/TorchVision
                                                        ↓
                                      shared temporary artifact volume
```

Compose services are `frontend`, `api`, `worker`, `beat`, `redis`, and
`postgres`. Generated artifacts are kept in the ignored `data` volume and are
eligible for cleanup after 24 hours.

## Run the complete application (recommended)

### Requirements

- Docker Desktop or Docker Engine with the Compose plugin
- 4 GB or more available memory
- macOS, Linux, or Windows with a working Docker VM

From the repository root:

```bash
docker compose up --build
```

Open:

- Workbench: <http://localhost:5173>
- Swagger API docs: <http://localhost:8000/docs>
- Liveness: <http://localhost:8000/healthz>
- Readiness (database and Redis): <http://localhost:8000/readyz>
- Metrics: <http://localhost:8000/metrics>

For a background start:

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f api worker
```

Stop containers while keeping data with `docker compose down`. To reset the
local PostgreSQL database and generated artifacts, use `docker compose down -v`.

### Use the workbench

1. Select a PNG, JPEG, or WebP smaller than 10 MB.
2. Let the local recommendation suggest **Line art** (one-ink marks,
   signatures, sketches) or **Illustration** (flat logos, icons, and multiple
   colours). You can override it.
3. Tune colour layers, path smoothing, minimum component area, and optional
   foreground segmentation.
4. Click **Vectorize image**. The UI shows Starting, Queued, and Processing
   states, retries temporary network/server failures, and polls the job.
5. Inspect the original and exact SVG preview side by side. Review the quality
   panel before using the result, then download SVG or comparison PNG.

Foreground segmentation is a background-removal mask, not a separate
vectorizer. Leave it off for clean transparent icons and simple logos; enable
it for noisy paper, shadows, or cluttered backgrounds. The OpenCV fallback is
always available.

## Supported and unsupported inputs

Best results come from high-contrast artwork with clear shapes. The quality
report detects photo-like, screenshot-like, spreadsheet/document-like,
dense-text, blank, and corrupt inputs. Photos may be rejected or marked
unsupported because this product is not a photo-vectorization system. A result
marked **Review recommended** is not a guarantee of visual fidelity.

See the complete fixture matrix in [samples/README.md](samples/README.md).

## Optional pretrained segmentation model

OpenCV is the dependable default. The optional model is TorchVision
`DeepLabV3-MobileNetV3-Large`; weights are never downloaded during inference
and no checkpoint is committed to Git. Download the pinned, checksum-verified
file once:

```bash
mkdir -p models
docker compose build api
docker compose run --rm api python scripts/download_segmentation_model.py \
  --destination /app/models/deeplabv3_mobilenet_v3_large-fc3c493d.pth
docker compose up -d --build
```

The API records provider, architecture, checkpoint, SHA-256 digest, whether
the model was requested, and the fallback reason. See
[docs/model.md](docs/model.md) for provenance, licensing, and later fine-tuning
guidance. Fine-tuning requires a user-provided image/mask dataset and measured
validation metrics; VectorForge does not train from scratch.

## REST API

Submit a job with multipart form data:

```bash
curl -X POST http://localhost:8000/api/v1/vectorizations \
  -H 'Idempotency-Key: demo-transparent-icon-1' \
  -F 'image=@samples/transparent-icon.png' \
  -F 'mode=illustration' \
  -F 'color_count=6' \
  -F 'smoothing=0.45' \
  -F 'min_component_area=40' \
  -F 'use_segmentation_model=false'
```

The API returns `202 Accepted` with a job ID. Poll
`GET /api/v1/vectorizations/{id}` until `completed` or `failed`, then use the
artifact URLs for `original`, `svg`, `preview`, or `comparison`. Reusing the
same idempotency key with the same source/options returns the original job;
using it for a different request returns `409`. Full contracts are in
[docs/api.md](docs/api.md).

## Quality and safety metadata

Completed jobs include an explainable quality report containing score/level,
warnings, foreground coverage, SVG path count, retained colours, removed
components, preview similarity, SVG complexity, input classification, and
model/fallback metadata. It is a health signal for review—not a benchmark of
model accuracy. Empty or pathless SVGs are never presented as successful.

## Local development

Use Python 3.12 and Node.js 22+; run Redis and PostgreSQL separately or use
Compose for those dependencies.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt pytest ruff

# API
cd backend
PYTHONPATH=. ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# In another terminal: worker
cd backend
PYTHONPATH=. ../.venv/bin/celery -A app.tasks.celery_app worker --loglevel=INFO

# In another terminal: frontend
cd frontend
npm ci
npm run dev
```

## Verification and tests

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
PYTHONPATH=backend .venv/bin/python -m ruff check backend/app backend/tests
cd frontend
npm run lint
npm run test
npm run build
```

The test suite covers decoding and limits, EXIF orientation, segmentation
fallback/model loading, quantization, filtering, contours, Bézier serialization,
SVG validity, quality classification, API contracts, idempotency, retry-safe
workers, and React reducer/API behavior. Docker Compose smoke testing should
upload a sample, wait for completion, validate the SVG, and download preview
and comparison artifacts.

## Troubleshooting

If the UI shows a temporary error, keep `docker compose logs -f api worker`
running while clicking **Vectorize image**. The API should return `202` and the
worker should log a task. If there is no request log, inspect the browser
Network tab and confirm the request is `/api/v1/vectorizations` through port
5173. Rebuild a changed frontend with:

```bash
docker compose up -d --build frontend
```

For a broken local Vite install (`Cannot find module ... vite/dist/...`):

```bash
cd frontend
npm ci
npm run dev
```

Do not commit model weights, uploaded images, credentials, or generated
artifacts. Every material code/configuration/test/documentation change and
every real error is recorded in [LEARNINGS.md](LEARNINGS.md).

## Scope and roadmap

Current work focuses on Phase 1 reliability: quality scoring, unsupported-input
detection, explainable model metadata, idempotency, retry-safe jobs, fixtures,
and clear diagnostics. The planned next phase evaluates additional compatible
pretrained models without downloading at inference time. Batch ZIP workflows,
webhooks, SDKs, Figma/Adobe integrations, cloud hosting, authentication,
billing, and enterprise deployment guides are intentionally out of scope for
now.

See [PROJECT.md](PROJECT.md), [AGENTS.md](AGENTS.md),
[docs/architecture.md](docs/architecture.md), [docs/quality.md](docs/quality.md),
and [docs/model.md](docs/model.md) for maintainer-level detail.

## License and third-party notices

This project is distributed under the repository [LICENSE](LICENSE). Review
TorchVision's BSD-3-Clause license and the terms accompanying its pretrained
weights before redistribution. No third-party weights are included in this
repository.
