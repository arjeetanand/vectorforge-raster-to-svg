from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.db import Base, migrate_vectorizations_schema
from app.models import JobStatus, Vectorization
from app.tasks import queue_vectorization


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine, expire_on_commit=False)
    queued_job_ids: list[str] = []

    def override_db():
        db = test_sessions()
        try:
            yield db
        finally:
            db.close()

    async def persist_test_upload(upload: UploadFile, job_id: str) -> dict:
        raw = await upload.read()
        artifact_dir = tmp_path / job_id
        artifact_dir.mkdir()
        (artifact_dir / "source.png").write_bytes(raw)
        return {
            "artifact_dir": str(artifact_dir),
            "filename": upload.filename or "upload.png",
            "mime_type": "image/png",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "width": 4,
            "height": 4,
        }

    monkeypatch.setattr(routes, "persist_upload", persist_test_upload)
    monkeypatch.setattr(
        routes.queue_vectorization,
        "delay",
        lambda job_id: queued_job_ids.append(job_id),
    )
    test_app = FastAPI()
    test_app.include_router(routes.router)
    test_app.dependency_overrides[routes.get_db] = override_db
    with TestClient(test_app) as client:
        yield client, queued_job_ids, tmp_path
    Base.metadata.drop_all(engine)
    engine.dispose()


def _submit(
    client: TestClient,
    payload: bytes,
    key: str,
    *,
    mode: str = "line-art",
) -> object:
    return client.post(
        "/api/v1/vectorizations",
        headers={"Idempotency-Key": key},
        data={
            "mode": mode,
            "color_count": 6,
            "smoothing": 0.5,
            "min_component_area": 24,
        },
        files={"image": ("mark.png", payload, "image/png")},
    )


def test_same_idempotency_key_and_request_replays_existing_job(api_client) -> None:
    client, queued_job_ids, artifact_root = api_client
    first = _submit(client, b"same-image", "replay-key")
    replay = _submit(client, b"same-image", "replay-key")

    assert first.status_code == 202
    assert replay.status_code == 202
    assert replay.json()["id"] == first.json()["id"]
    assert queued_job_ids == [first.json()["id"]]
    # The duplicate upload is staged only long enough to compare its content,
    # then removed without touching the original job's artifact directory.
    assert len(list(artifact_root.iterdir())) == 1


@pytest.mark.parametrize(
    ("payload", "mode"),
    [(b"different-image", "line-art"), (b"same-image", "illustration")],
)
def test_reused_idempotency_key_with_different_request_is_a_conflict(
    api_client, payload: bytes, mode: str
) -> None:
    client, queued_job_ids, artifact_root = api_client
    first = _submit(client, b"same-image", "conflict-key")
    conflict = _submit(client, payload, "conflict-key", mode=mode)

    assert first.status_code == 202
    assert conflict.status_code == 409
    assert (
        "different source image or vectorization settings" in conflict.json()["detail"]
    )
    assert queued_job_ids == [first.json()["id"]]
    assert len(list(artifact_root.iterdir())) == 1


def test_legacy_schema_migration_adds_diagnostics_and_deduplicates_keys(
    tmp_path: Path,
) -> None:
    legacy_engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'legacy.db'}")
    with legacy_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE vectorizations ("
                "id VARCHAR(36) PRIMARY KEY, "
                "idempotency_key VARCHAR(255), "
                "created_at DATETIME"
                ")"
            )
        )
        connection.execute(
            text(
                "INSERT INTO vectorizations (id, idempotency_key, created_at) "
                "VALUES ('older', 'legacy-key', :older_at), "
                "('newer', 'legacy-key', :newer_at)"
            ),
            {
                "older_at": datetime(2025, 1, 1, tzinfo=UTC),
                "newer_at": datetime(2025, 2, 1, tzinfo=UTC),
            },
        )

    migrate_vectorizations_schema(legacy_engine)

    with legacy_engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, idempotency_key FROM vectorizations ORDER BY id")
        ).all()
    assert rows == [("newer", None), ("older", "legacy-key")]
    column_names = {
        column["name"]
        for column in inspect(legacy_engine).get_columns("vectorizations")
    }
    assert "diagnostics" in column_names
    with pytest.raises(Exception):
        with legacy_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO vectorizations (id, idempotency_key) "
                    "VALUES ('duplicate', 'legacy-key')"
                )
            )
    legacy_engine.dispose()


def test_worker_ignores_nonqueued_jobs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    engine = create_engine("sqlite+pysqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(UTC)
    with test_sessions.begin() as db:
        for job_status in (JobStatus.PROCESSING, JobStatus.COMPLETED, JobStatus.FAILED):
            db.add(
                Vectorization(
                    id=job_status.value,
                    status=job_status,
                    source_filename="source.png",
                    source_mime_type="image/png",
                    source_sha256="a" * 64,
                    options={"mode": "line-art"},
                    artifact_dir=str(tmp_path / job_status.value),
                    source_width=4,
                    source_height=4,
                    started_at=now if job_status == JobStatus.PROCESSING else None,
                    completed_at=now if job_status != JobStatus.PROCESSING else None,
                )
            )

    import app.tasks as task_module

    monkeypatch.setattr(task_module, "SessionLocal", test_sessions)
    for job_status in (JobStatus.PROCESSING, JobStatus.COMPLETED, JobStatus.FAILED):
        queue_vectorization.run(job_status.value)

    with test_sessions() as db:
        statuses = dict(
            db.execute(select(Vectorization.id, Vectorization.status)).all()
        )
    assert statuses == {
        "processing": JobStatus.PROCESSING,
        "completed": JobStatus.COMPLETED,
        "failed": JobStatus.FAILED,
    }
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_batch_multipart_creates_independent_jobs_and_replays(api_client, monkeypatch):
    client, queued_job_ids, artifact_root = api_client

    def persist_bytes(raw, filename, job_id, settings=None):
        path = artifact_root / job_id
        path.mkdir()
        (path / "source.png").write_bytes(raw)
        return {
            "artifact_dir": str(path),
            "filename": filename,
            "mime_type": "image/png",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "width": 4,
            "height": 4,
        }

    monkeypatch.setattr(routes, "persist_upload_bytes", persist_bytes)
    files = [
        ("images", ("one.png", b"one", "image/png")),
        ("images", ("two.png", b"two", "image/png")),
    ]
    first = client.post(
        "/api/v1/vectorization-batches",
        headers={"Idempotency-Key": "batch-key"},
        data={"mode": "line-art"},
        files=files,
    )
    replay = client.post(
        "/api/v1/vectorization-batches",
        headers={"Idempotency-Key": "batch-key"},
        data={"mode": "line-art"},
        files=files,
    )
    assert first.status_code == 202
    assert len(first.json()["items"]) == 2
    assert replay.json()["id"] == first.json()["id"]
    assert len(queued_job_ids) == 2

    conflict = client.post(
        "/api/v1/vectorization-batches",
        headers={"Idempotency-Key": "batch-key"},
        data={"mode": "line-art"},
        files=[("images", ("one.png", b"different", "image/png"))],
    )
    assert conflict.status_code == 409


def test_batch_zip_rejects_unsafe_paths(api_client):
    client, _, _ = api_client
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as bundle:
        bundle.writestr("../escape.png", b"not-an-image")
    response = client.post(
        "/api/v1/vectorization-batches",
        files={"archive": ("batch.zip", stream.getvalue(), "application/zip")},
    )
    assert response.status_code == 422
    assert "safe ZIP" in response.json()["detail"]


def test_batch_zip_ignores_non_images_and_keeps_invalid_image_as_failed_item(
    api_client, monkeypatch
):
    client, queued_job_ids, artifact_root = api_client

    def persist_bytes(raw, filename, job_id, settings=None):
        if raw == b"corrupt":
            from fastapi import HTTPException

            raise HTTPException(status_code=422, detail="Upload must be a valid image.")
        path = artifact_root / job_id
        path.mkdir()
        (path / "source.png").write_bytes(raw)
        return {
            "artifact_dir": str(path),
            "filename": filename,
            "mime_type": "image/png",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "width": 4,
            "height": 4,
        }

    monkeypatch.setattr(routes, "persist_upload_bytes", persist_bytes)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as bundle:
        bundle.writestr("samples/README.md", b"documentation")
        bundle.writestr("samples/reference.svg", b"<svg />")
        bundle.writestr("samples/good.png", b"valid")
        bundle.writestr("samples/corrupt.jpg", b"corrupt")

    response = client.post(
        "/api/v1/vectorization-batches",
        files={"archive": ("samples.zip", stream.getvalue(), "application/zip")},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["total_count"] == 2
    assert body["completed_count"] == 0
    assert body["failed_count"] == 1
    assert len(queued_job_ids) == 1
    assert [item["status"] for item in body["items"]] == ["queued", "failed"]
