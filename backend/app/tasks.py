from __future__ import annotations

import inspect
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from celery import Celery

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


def _pipeline_output(output: Any, output_dir: Path) -> tuple[str, Path, Path, Path]:
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
    return model_used, svg, preview, comparison


@celery_app.task(name="vectorforge.vectorize", bind=True, acks_late=True)
def queue_vectorization(self, job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(Vectorization, job_id)
        if not job or job.status == JobStatus.COMPLETED:
            return
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now(UTC)
        job.error_code = None
        job.error_detail = None
        db.commit()
        try:
            from app.pipeline.vectorize import vectorize_image

            result = vectorize_image(
                source_path(job.artifact_dir), Path(job.artifact_dir), job.options
            )
            if inspect.isawaitable(result):
                raise RuntimeError(
                    "The pipeline entrypoint must be synchronous when run by Celery."
                )
            model_used, svg, preview, comparison = _pipeline_output(
                result, Path(job.artifact_dir)
            )
            if not all(path.is_file() for path in (svg, preview, comparison)):
                raise RuntimeError(
                    "Vectorization pipeline did not produce all required artifacts."
                )
            job.status = JobStatus.COMPLETED
            job.model_used = model_used
            job.completed_at = datetime.now(UTC)
            db.commit()
        except Exception:
            db.rollback()
            failed = db.get(Vectorization, job_id)
            if failed:
                failed.status = JobStatus.FAILED
                failed.error_code = "processing_failed"
                # Deliberately do not store raw exceptions, paths, or stack traces.
                failed.error_detail = (
                    "Vectorization could not be completed. Adjust the input or retry."
                )
                failed.completed_at = datetime.now(UTC)
                db.commit()
            raise
    finally:
        db.close()


@celery_app.task(name="vectorforge.cleanup_artifacts")
def cleanup_artifacts() -> int:
    return cleanup_expired_artifacts()
