# VectorForge

VectorForge turns sketches, logos, and flat-color icons into editable SVG paths. It is designed for local use and deliberately does not promise photo vectorization.

## Architecture

The Docker Compose stack contains a FastAPI API, Celery worker, Redis broker, PostgreSQL metadata database, React workbench, and an ignored `data/` volume for temporary artifacts. The API accepts an image and returns a job identifier; the worker runs segmentation and vectorization before the UI downloads the SVG or comparison preview.

## Run with Docker (recommended)

### Prerequisites

- Docker Desktop or Docker Engine with the Compose plugin.
- At least 4 GB of free memory for the API, worker, database, and optional ML dependencies.

### Start the complete application

```bash
# From the repository root
docker compose up --build
```

Wait until the API and worker report that they are ready, then open:

- Workbench: `http://localhost:5173`
- API documentation: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/healthz`

### Use the workbench

1. Open `http://localhost:5173`.
2. Drop or select a PNG, JPEG, or WebP image smaller than 10 MB.
3. Use the automatic recommendation as a starting point: **Line art** is for a signature, sketch, or one-ink mark; **Illustration** is for flat artwork and multi-colour logos.
4. Adjust color layers, smoothing, and minimum detail area if needed. When a setting is changed after a completed conversion, VectorForge clears that older result and its downloads so it cannot be mistaken for the new settings.
5. Select **Vectorize image** after uploading or changing settings, then wait for the status timeline to complete.
6. Download the generated SVG or comparison PNG.

### Read the quality report

Completed jobs include a **Conversion quality** panel. It shows the SVG path and
colour-layer counts, components removed as noise, foreground coverage, SVG
complexity, preview-similarity indicator, model/fallback used, and any warnings.
This is an explainable output-health check—not a claim that a heuristic or
pretrained model is perfectly accurate. A **Review recommended** or
**Unsupported input** result means inspect the SVG before using it in production.
See [quality-report documentation](docs/quality.md) for the exact fields.

### Automatic recommendation

The workbench performs a small, local browser-side analysis; it does not upload the image or call an LLM to choose a mode. It distinguishes meaningful artwork colour families from a dominant white background, so a sparse multi-colour logo starts in **Illustration** while a one-ink signature starts in **Line art**. You can always override the choice before vectorizing.

### Try the full sample test pack

The repository includes supported-artwork and deliberate-failure inputs in [samples/README.md](samples/README.md). Follow its test matrix to check line art, illustration, alpha transparency, noisy backgrounds, photos/documents outside scope, blank images, corrupt files, and the upload-size limit.

The default OpenCV foreground detector works immediately. Turn on **Foreground segmentation** only when you have installed the optional model below; otherwise the job completes with an explicit OpenCV fallback.

### Optional PyTorch foreground model

The app does not download weights automatically. To use the pinned DeepLabV3-MobileNetV3-Large checkpoint, download it once before starting Compose:

```bash
mkdir -p models
docker compose build api
docker compose run --rm api python scripts/download_segmentation_model.py \
  --destination /app/models/deeplabv3_mobilenet_v3_large-fc3c493d.pth
docker compose up --build
```

Compose mounts `./models` read-only into the worker. Do not commit checkpoint files.

### Stop or reset the app

```bash
# Stop containers but retain generated jobs and PostgreSQL data.
docker compose down

# Stop containers and remove all local Compose data.
docker compose down -v
```

## Run without Docker (development)

Use Python 3.12 and Node.js 22 or newer. Start Redis and PostgreSQL separately, then configure `VECTORFORGE_DATABASE_URL`, `VECTORFORGE_REDIS_URL`, and `VECTORFORGE_ARTIFACT_ROOT` for your machine.

```bash
# Terminal 1 — backend environment and API
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt pytest ruff
cd backend
PYTHONPATH=. ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — Celery worker
cd backend
PYTHONPATH=. ../.venv/bin/celery -A app.tasks.celery_app worker --loglevel=INFO

# Terminal 3 — React workbench
cd frontend
npm ci
npm run dev
```

## Verify the installation

```bash
# Backend checks
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
PYTHONPATH=backend .venv/bin/python -m ruff check backend/app backend/tests

# Frontend checks
cd frontend
npm run lint
npm run test
npm run build
```

## Troubleshooting

### `Cannot find module ... vite/dist/node/chunks/dist.js`

This is a damaged or incomplete local `frontend/node_modules` install. The Docker Compose frontend does not run Vite; it serves the built application through Nginx. If you are using local development mode, restore dependencies from the lockfile and restart Vite:

```bash
cd frontend
npm ci
npm run dev
```

Do not use `npm install` as a substitute for `npm ci` when repairing this project: `npm ci` recreates exactly the dependency tree pinned in `package-lock.json`.

## Limitations

- Best results: high-contrast line art, logos, and flat illustrations.
- Not supported: spreadsheets, screenshots of documents, photographs, or dense text. If no eligible artwork contours are found, the job fails instead of producing an empty SVG.
- Output is editable filled SVG paths. It does not infer semantic layers or stroke centerlines.
- A classical OpenCV mask is always available. Optional PyTorch segmentation requires an explicitly downloaded model; no weights are committed.
- The quality report warns about photo-like, document-like, screenshot-like, or dense-text-like inputs when detectable, but it does not convert VectorForge into an OCR or photo-vectorization tool.

## Development quality gates

Run the backend tests and static checks from `backend/`, and frontend tests/build from `frontend/`. Every material change and genuine error is summarized in [LEARNINGS.md](LEARNINGS.md).

See [architecture documentation](docs/architecture.md), [API documentation](docs/api.md), and [model documentation](docs/model.md) for implementation details.
