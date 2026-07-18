# VectorForge

VectorForge turns sketches, logos, and flat-color icons into editable SVG paths. It is designed for local use and deliberately does not promise photo vectorization.

## Architecture

The Docker Compose stack contains a FastAPI API, Celery worker, Redis broker, PostgreSQL metadata database, React workbench, and an ignored `data/` volume for temporary artifacts. The API accepts an image and returns a job identifier; the worker runs segmentation and vectorization before the UI downloads the SVG or comparison preview.

## Quick start

```bash
docker compose up --build
```

Open `http://localhost:5173` for the workbench and `http://localhost:8000/docs` for OpenAPI. See [architecture documentation](docs/architecture.md), [API documentation](docs/api.md), and [model documentation](docs/model.md).

## Limitations

- Best results: high-contrast line art, logos, and flat illustrations.
- Output is editable filled SVG paths. It does not infer semantic layers or stroke centerlines.
- A classical OpenCV mask is always available. Optional PyTorch segmentation requires an explicitly downloaded model; no weights are committed.

## Development quality gates

Run the backend tests and static checks from `backend/`, and frontend tests/build from `frontend/`. Every material change and genuine error is summarized in [LEARNINGS.md](LEARNINGS.md).
