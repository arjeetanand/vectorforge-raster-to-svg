from __future__ import annotations

import shutil
import uuid

from celery.exceptions import OperationalError
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import JobStatus, Vectorization
from app.schemas import (
    ArtifactUrls,
    QualityReport,
    VectorizationOptions,
    VectorizationResponse,
)
from app.services.storage import artifact_path, persist_upload
from app.tasks import queue_vectorization

router = APIRouter(prefix="/api/v1")
system_router = APIRouter()


def _urls(request: Request, job: Vectorization) -> ArtifactUrls:
    base = f"{request.base_url}api/v1/vectorizations/{job.id}/artifacts"
    if job.status == JobStatus.COMPLETED:
        return ArtifactUrls(
            original=f"{base}/original",
            svg=f"{base}/svg",
            preview=f"{base}/preview",
            comparison=f"{base}/comparison",
        )
    return ArtifactUrls(original=f"{base}/original")


def _response(request: Request, job: Vectorization) -> VectorizationResponse:
    return VectorizationResponse(
        id=job.id,
        status=job.status,
        source_filename=job.source_filename,
        options=VectorizationOptions.model_validate(job.options),
        source_width=job.source_width,
        source_height=job.source_height,
        model_used=job.model_used,
        quality=_quality(job),
        error_code=job.error_code,
        error_detail=job.error_detail,
        artifacts=_urls(request, job),
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


def _quality(job: Vectorization) -> QualityReport | None:
    """Avoid breaking existing jobs if a pre-migration diagnostics value is malformed."""

    if not job.diagnostics:
        return None
    try:
        return QualityReport.model_validate(job.diagnostics)
    except ValueError:
        return None


def _same_idempotent_request(
    job: Vectorization, source_sha256: str, options: VectorizationOptions
) -> bool:
    return job.source_sha256 == source_sha256 and job.options == options.model_dump(
        mode="json"
    )


def _discard_staged_upload(artifact_dir: str) -> None:
    """Remove a duplicate request's private staging directory before returning."""

    shutil.rmtree(artifact_dir, ignore_errors=True)


def _idempotency_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "This Idempotency-Key was already used for a different source image "
            "or vectorization settings."
        ),
    )


@router.post(
    "/vectorizations",
    response_model=VectorizationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_vectorization(
    request: Request,
    image: UploadFile = File(...),
    mode: str = Form("line-art"),
    color_count: int = Form(6),
    smoothing: float = Form(0.5),
    min_component_area: int = Form(24),
    use_segmentation_model: bool = Form(False),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> VectorizationResponse:
    try:
        options = VectorizationOptions(
            mode=mode,
            color_count=color_count,
            smoothing=smoothing,
            min_component_area=min_component_area,
            use_segmentation_model=use_segmentation_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if idempotency_key is not None and not idempotency_key.strip():
        raise HTTPException(
            status_code=422, detail="Idempotency-Key must not be blank."
        )
    if idempotency_key is not None and len(idempotency_key) > 255:
        raise HTTPException(
            status_code=422, detail="Idempotency-Key must be 255 characters or fewer."
        )

    job_id = str(uuid.uuid4())
    stored = await persist_upload(image, job_id)
    if idempotency_key:
        existing = db.scalar(
            select(Vectorization).where(
                Vectorization.idempotency_key == idempotency_key
            )
        )
        if existing:
            _discard_staged_upload(stored["artifact_dir"])
            if _same_idempotent_request(existing, stored["sha256"], options):
                return _response(request, existing)
            raise _idempotency_conflict()

    job = Vectorization(
        id=job_id,
        status=JobStatus.QUEUED,
        source_filename=stored["filename"],
        source_mime_type=stored["mime_type"],
        source_sha256=stored["sha256"],
        idempotency_key=idempotency_key,
        options=options.model_dump(),
        artifact_dir=stored["artifact_dir"],
        source_width=stored["width"],
        source_height=stored["height"],
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError as exc:
        # A parallel request may have claimed this key after our lookup. The
        # database index is the final authority; reconcile against its job
        # instead of queueing duplicate work.
        db.rollback()
        _discard_staged_upload(stored["artifact_dir"])
        if idempotency_key:
            existing = db.scalar(
                select(Vectorization).where(
                    Vectorization.idempotency_key == idempotency_key
                )
            )
            if existing and _same_idempotent_request(
                existing, stored["sha256"], options
            ):
                return _response(request, existing)
            raise _idempotency_conflict() from exc
        raise HTTPException(
            status_code=500, detail="Vectorization job could not be created."
        ) from exc
    db.refresh(job)
    try:
        queue_vectorization.delay(job.id)
    except OperationalError as exc:
        job.status = JobStatus.FAILED
        job.error_code = "queue_unavailable"
        job.error_detail = "The processing queue is temporarily unavailable."
        db.commit()
        raise HTTPException(status_code=503, detail=job.error_detail) from exc
    return _response(request, job)


@router.get("/vectorizations/{job_id}", response_model=VectorizationResponse)
def get_vectorization(
    job_id: str, request: Request, db: Session = Depends(get_db)
) -> VectorizationResponse:
    job = db.get(Vectorization, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Vectorization job not found.")
    return _response(request, job)


@router.get("/vectorizations/{job_id}/artifacts/{artifact_name}")
def get_artifact(
    job_id: str, artifact_name: str, db: Session = Depends(get_db)
) -> FileResponse:
    job = db.get(Vectorization, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Vectorization job not found.")
    try:
        path, media_type = artifact_path(job.artifact_dir, artifact_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown artifact.") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Artifact not available.") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not available.")
    return FileResponse(path, media_type=media_type, filename=path.name)


@system_router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@system_router.get("/readyz")
def readyz(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable.") from exc
    return {"status": "ready"}


@system_router.get("/metrics", response_class=PlainTextResponse)
def metrics(db: Session = Depends(get_db)) -> str:
    queued = (
        db.query(Vectorization).filter(Vectorization.status == JobStatus.QUEUED).count()
    )
    processing = (
        db.query(Vectorization)
        .filter(Vectorization.status == JobStatus.PROCESSING)
        .count()
    )
    completed = (
        db.query(Vectorization)
        .filter(Vectorization.status == JobStatus.COMPLETED)
        .count()
    )
    failed = (
        db.query(Vectorization).filter(Vectorization.status == JobStatus.FAILED).count()
    )
    return "\n".join(
        [
            "# TYPE vectorforge_jobs gauge",
            f'vectorforge_jobs{{status="queued"}} {queued}',
            f'vectorforge_jobs{{status="processing"}} {processing}',
            f'vectorforge_jobs{{status="completed"}} {completed}',
            f'vectorforge_jobs{{status="failed"}} {failed}',
            "",
        ]
    )
