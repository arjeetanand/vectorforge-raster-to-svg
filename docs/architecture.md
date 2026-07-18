# Architecture

`frontend` uploads the selected raster to `api`. The API validates and stores the input under a generated job ID, records a queued vectorization in PostgreSQL, and sends a Celery task through Redis. The worker owns image preprocessing, foreground segmentation, contour tracing, SVG generation, and preview rendering. Generated artifacts are retained in `data/vectorizations/<id>/` until cleanup.

The API never loads model weights or performs vectorization inline. Workers are idempotent: a task for a terminal job exits without rewriting artifacts.
