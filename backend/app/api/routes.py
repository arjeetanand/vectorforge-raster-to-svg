from __future__ import annotations

import shutil
import uuid
import hashlib
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

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
from fastapi.responses import FileResponse, PlainTextResponse, Response
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import JobStatus, Vectorization, VectorizationBatch
from app.schemas import (
    ArtifactUrls,
    QualityReport,
    VectorizationOptions,
    VectorizationResponse,
    BatchVectorizationResponse,
)
from app.services.storage import artifact_path, persist_upload, persist_upload_bytes
from app.services.batch_artifacts import create_batch_zip, report_bytes
from app.services.presets import list_presets
from app.core.config import get_settings
from app.tasks import queue_vectorization

router = APIRouter(prefix="/api/v1")
system_router = APIRouter()

_BATCH_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})


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


def _batch_response(
    request: Request, batch: VectorizationBatch, db: Session
) -> BatchVectorizationResponse:
    items = list(
        db.scalars(
            select(Vectorization)
            .where(Vectorization.batch_id == batch.id)
            .order_by(Vectorization.batch_index)
        )
    )
    completed = sum(item.status == JobStatus.COMPLETED for item in items)
    failed = sum(item.status == JobStatus.FAILED for item in items)
    active = sum(
        item.status in (JobStatus.QUEUED, JobStatus.PROCESSING) for item in items
    )
    if active:
        batch.status = (
            "processing"
            if any(item.status == JobStatus.PROCESSING for item in items)
            else "queued"
        )
    elif failed and completed:
        batch.status = "partial"
    elif failed:
        batch.status = "failed"
    else:
        batch.status = "completed"
    return BatchVectorizationResponse(
        id=batch.id,
        status=batch.status,
        total_count=len(items),
        completed_count=completed,
        failed_count=failed,
        items=[_response(request, item) for item in items],
        created_at=batch.created_at,
        updated_at=batch.updated_at,
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


@router.get("/presets")
def get_presets() -> list[dict]:
    return list_presets()


@router.post(
    "/vectorization-batches",
    response_model=BatchVectorizationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_vectorization_batch(
    request: Request,
    images: list[UploadFile] = File(default=[]),
    archive: UploadFile | None = File(default=None),
    mode: str = Form("line-art"),
    color_count: int = Form(6),
    smoothing: float = Form(0.5),
    min_component_area: int = Form(24),
    use_segmentation_model: bool = Form(False),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> BatchVectorizationResponse:
    """Create up to 100 independent jobs from multipart images or one ZIP archive."""
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
    if idempotency_key and (not idempotency_key.strip() or len(idempotency_key) > 255):
        raise HTTPException(
            status_code=422,
            detail="Idempotency-Key must be 255 characters or fewer and not blank.",
        )
    if archive is not None and images:
        raise HTTPException(
            status_code=422, detail="Submit images or an archive, not both."
        )
    entries: list[tuple[str, bytes]] = []
    if archive is not None:
        raw_archive = await archive.read(50 * 1024 * 1024 + 1)
        if len(raw_archive) > 50 * 1024 * 1024:
            raise HTTPException(
                status_code=413, detail="Batch archives are limited to 50 MB."
            )
        try:
            with zipfile.ZipFile(io.BytesIO(raw_archive)) as bundle:
                for info in bundle.infolist():
                    if info.is_dir() or info.filename.startswith("__MACOSX/"):
                        continue
                    safe_name = info.filename.replace("\\", "/")
                    if safe_name.startswith("/") or ".." in safe_name.split("/"):
                        raise ValueError("archive contains an unsafe path")
                    # ZIPs commonly contain SVG references, README files, and
                    # Finder metadata. They are not conversion inputs; ignore
                    # them instead of failing the entire batch.
                    if Path(safe_name).suffix.lower() not in _BATCH_IMAGE_SUFFIXES:
                        continue
                    entries.append((safe_name, bundle.read(info)))
        except (zipfile.BadZipFile, OSError, ValueError) as exc:
            raise HTTPException(
                status_code=422, detail="Archive must be a valid, safe ZIP file."
            ) from exc
    else:
        entries = [
            (upload.filename or "upload", await upload.read()) for upload in images
        ]
    if not entries:
        raise HTTPException(
            status_code=422,
            detail="The batch contains no supported PNG, JPEG, or WebP images.",
        )
    if len(entries) > 100:
        raise HTTPException(
            status_code=413, detail="A batch may contain at most 100 images."
        )
    fingerprint = hashlib.sha256()
    for name, raw in entries:
        fingerprint.update(name.encode("utf-8", "replace"))
        fingerprint.update(raw)
    fingerprint.update(str(options.model_dump(mode="json")).encode())
    if idempotency_key:
        existing_batch = db.scalar(
            select(VectorizationBatch).where(
                VectorizationBatch.idempotency_key == idempotency_key
            )
        )
        if existing_batch:
            if (
                existing_batch.total_count == len(entries)
                and existing_batch.source_fingerprint == fingerprint.hexdigest()
            ):
                return _batch_response(request, existing_batch, db)
            raise _idempotency_conflict()
    batch = VectorizationBatch(
        id=str(uuid.uuid4()),
        idempotency_key=idempotency_key,
        source_fingerprint=fingerprint.hexdigest(),
        total_count=len(entries),
        status="queued",
    )
    db.add(batch)
    staged: list[str] = []
    try:
        for index, (name, raw) in enumerate(entries):
            job_id = str(uuid.uuid4())
            try:
                stored = persist_upload_bytes(raw, name, job_id)
                staged.append(stored["artifact_dir"])
                db.add(
                    Vectorization(
                        id=job_id,
                        status=JobStatus.QUEUED,
                        source_filename=stored["filename"],
                        source_mime_type=stored["mime_type"],
                        source_sha256=stored["sha256"],
                        options=options.model_dump(),
                        artifact_dir=stored["artifact_dir"],
                        source_width=stored["width"],
                        source_height=stored["height"],
                        batch_id=batch.id,
                        batch_index=index,
                    )
                )
            except HTTPException as exc:
                # A bad member should be visible as one failed item while
                # valid siblings continue through Celery. Do not store the
                # invalid bytes or raw exception details.
                db.add(
                    Vectorization(
                        id=job_id,
                        status=JobStatus.FAILED,
                        source_filename=Path(name).name[:255],
                        source_mime_type="application/octet-stream",
                        source_sha256=hashlib.sha256(raw).hexdigest(),
                        options=options.model_dump(),
                        artifact_dir=str(get_settings().artifact_root / job_id),
                        source_width=0,
                        source_height=0,
                        error_code="invalid_batch_item",
                        error_detail=str(exc.detail),
                        completed_at=datetime.now(UTC),
                        batch_id=batch.id,
                        batch_index=index,
                    )
                )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        for path in staged:
            _discard_staged_upload(path)
        if idempotency_key:
            existing_batch = db.scalar(
                select(VectorizationBatch).where(
                    VectorizationBatch.idempotency_key == idempotency_key
                )
            )
            if (
                existing_batch
                and existing_batch.source_fingerprint == fingerprint.hexdigest()
            ):
                return _batch_response(request, existing_batch, db)
            raise _idempotency_conflict() from exc
        raise HTTPException(
            status_code=500, detail="Vectorization batch could not be created."
        ) from exc
    except Exception:
        db.rollback()
        for path in staged:
            _discard_staged_upload(path)
        raise
    items = list(
        db.scalars(
            select(Vectorization)
            .where(Vectorization.batch_id == batch.id)
            .order_by(Vectorization.batch_index)
        )
    )
    try:
        for item in items:
            if item.status == JobStatus.QUEUED:
                queue_vectorization.delay(item.id)
    except OperationalError as exc:
        # Jobs remain durable and can be retried after Redis recovers.
        raise HTTPException(
            status_code=503, detail="The processing queue is temporarily unavailable."
        ) from exc
    return _batch_response(request, batch, db)


@router.get(
    "/vectorization-batches/{batch_id}", response_model=BatchVectorizationResponse
)
def get_vectorization_batch(
    batch_id: str, request: Request, db: Session = Depends(get_db)
) -> BatchVectorizationResponse:
    batch = db.get(VectorizationBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Vectorization batch not found.")
    return _batch_response(request, batch, db)


@router.post(
    "/vectorization-batches/{batch_id}/retry-failed",
    response_model=BatchVectorizationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_failed_batch(
    batch_id: str, request: Request, db: Session = Depends(get_db)
) -> BatchVectorizationResponse:
    batch = db.get(VectorizationBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Vectorization batch not found.")
    failed = list(
        db.scalars(
            select(Vectorization).where(
                Vectorization.batch_id == batch.id,
                Vectorization.status == JobStatus.FAILED,
            )
        )
    )
    if not failed:
        return _batch_response(request, batch, db)
    for item in failed:
        item.status = JobStatus.QUEUED
        item.error_code = None
        item.error_detail = None
        item.completed_at = None
    batch.status = "queued"
    db.commit()
    for item in failed:
        queue_vectorization.delay(item.id)
    return _batch_response(request, batch, db)


@router.get("/vectorization-batches/{batch_id}/artifacts/{artifact_name}")
def get_batch_artifact(
    batch_id: str, artifact_name: str, db: Session = Depends(get_db)
):
    batch = db.get(VectorizationBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Vectorization batch not found.")
    items = list(
        db.scalars(
            select(Vectorization)
            .where(Vectorization.batch_id == batch.id)
            .order_by(Vectorization.batch_index)
        )
    )
    if any(item.status in (JobStatus.QUEUED, JobStatus.PROCESSING) for item in items):
        raise HTTPException(
            status_code=409,
            detail="Batch artifacts are available after processing completes.",
        )
    entries = []
    for item in items:
        svg = Path(item.artifact_dir) / "vector.svg"
        entries.append(
            {
                "file": item.source_filename,
                "status": item.status.value,
                "id": item.id,
                "quality": item.diagnostics,
                "model_used": item.model_used,
                "error_code": item.error_code,
                "svg_path": str(svg) if svg.is_file() else None,
            }
        )
    batch_dir = get_settings().artifact_root / batch.id
    batch_dir.mkdir(parents=True, exist_ok=True)
    if artifact_name in {"report.json", "report.csv"}:
        json_bytes, csv_bytes = report_bytes(entries)
        if artifact_name == "report.json":
            return Response(
                json_bytes,
                media_type="application/json",
                headers={"Content-Disposition": 'attachment; filename="report.json"'},
            )
        return Response(
            csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="report.csv"'},
        )
    if artifact_name == "results.zip":
        archive = create_batch_zip(
            get_settings().artifact_root,
            entries,
            archive_name=f"{batch.id}-results.zip",
        )
        destination = batch_dir / "results.zip"
        archive.replace(destination)
        return FileResponse(
            destination,
            media_type="application/zip",
            filename="vectorforge-results.zip",
        )
    raise HTTPException(status_code=404, detail="Unknown batch artifact.")


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
