from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from celery import Celery
from sqlalchemy import update

from app.core.config import get_settings
from app.db import SessionLocal
from app.models import JobStatus, Vectorization
from app.services.storage import cleanup_expired_artifacts, source_path

settings = get_settings()
celery_app = Celery(
    "vectorforge", broker=settings.redis_url, backend=settings.redis_url
)
celery_app.conf.update(
    task_always_eager=settings.task_always_eager,
    task_track_started=True,
    timezone="UTC",
    beat_schedule={
        "cleanup-expired-artifacts-hourly": {
            "task": "vectorforge.cleanup_artifacts",
            "schedule": 3600.0,
        }
    },
)


def _pipeline_output(
    output: Any, output_dir: Path
) -> tuple[str, Path, Path, Path, dict[str, Any] | None]:
    """Accept the documented pipeline result object or a small mapping for testability."""

    def get(name: str, default: Any = None) -> Any:
        return (
            output.get(name, default)
            if isinstance(output, dict)
            else getattr(output, name, default)
        )

    model_used = str(get("model_used", "opencv-classical"))
    svg = Path(get("svg_path", output_dir / "vector.svg"))
    preview = Path(get("preview_path", output_dir / "preview.png"))
    comparison = Path(get("comparison_path", output_dir / "comparison.png"))
    quality = get("quality", get("quality_report"))
    if quality is not None and not isinstance(quality, Mapping):
        raise ValueError("Vectorization diagnostics must be a mapping.")
    if quality is not None:
        quality = dict(quality)
        # Fail safely before committing: job JSON metadata must never contain
        # arrays, paths, or arbitrary Python objects from a pipeline result.
        json.dumps(quality)
    return model_used, svg, preview, comparison, quality


@celery_app.task(name="vectorforge.vectorize", bind=True, acks_late=True)
def queue_vectorization(self, job_id: str) -> None:
    db = SessionLocal()
    try:
        # Atomically claim a queued job. Re-delivery, accidental duplicate
        # submission, and already-processing/terminal jobs must not rewrite
        # artifacts or restart a conversion.
        claim = db.execute(
            update(Vectorization)
            .where(
                Vectorization.id == job_id,
                Vectorization.status == JobStatus.QUEUED,
            )
            .values(
                status=JobStatus.PROCESSING,
                started_at=datetime.now(UTC),
                error_code=None,
                error_detail=None,
            )
        )
        db.commit()
        if claim.rowcount != 1:
            return
        job = db.get(Vectorization, job_id)
        if not job:
            return
        try:
            from app.pipeline.vectorize import NoVectorPathsError, vectorize_image

            result = vectorize_image(
                source_path(job.artifact_dir), Path(job.artifact_dir), job.options
            )
            if inspect.isawaitable(result):
                raise RuntimeError(
                    "The pipeline entrypoint must be synchronous when run by Celery."
                )
            model_used, svg, preview, comparison, quality = _pipeline_output(
                result, Path(job.artifact_dir)
            )
            if not all(path.is_file() for path in (svg, preview, comparison)):
                raise RuntimeError(
                    "Vectorization pipeline did not produce all required artifacts."
                )
            job.status = JobStatus.COMPLETED
            job.model_used = model_used
            job.diagnostics = quality
            job.completed_at = datetime.now(UTC)
            db.commit()
        except Exception as exc:
            db.rollback()
            failed = db.get(Vectorization, job_id)
            if failed:
                failed.status = JobStatus.FAILED
                no_paths = isinstance(exc, NoVectorPathsError)
                failed.error_code = (
                    "no_vector_paths" if no_paths else "processing_failed"
                )
                # Deliberately do not store raw exceptions, paths, or stack traces.
                failed.error_detail = (
                    "No editable shapes were detected. VectorForge works best with clear sketches, logos, and flat-colour artwork."
                    if no_paths
                    else "Vectorization could not be completed. Adjust the input or retry."
                )
                failed.completed_at = datetime.now(UTC)
                db.commit()
            raise
    finally:
        db.close()


@celery_app.task(name="vectorforge.cleanup_artifacts")
def cleanup_artifacts() -> int:
    return cleanup_expired_artifacts()
