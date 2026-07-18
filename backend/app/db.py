from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Import before metadata creation so all mapped tables are registered.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    migrate_vectorizations_schema(engine)


def migrate_vectorizations_schema(database_engine: Engine) -> None:
    """Apply small, additive compatibility changes to an existing jobs table.

    ``create_all`` only creates missing tables. It intentionally does not alter
    a PostgreSQL table that was created by an earlier VectorForge version, so
    additive fields and indexes used by the API must be handled explicitly.
    """

    inspector = inspect(database_engine)
    tables = set(inspector.get_table_names())
    if "vectorizations" not in tables:
        return

    column_names = {
        column["name"] for column in inspector.get_columns("vectorizations")
    }
    with database_engine.begin() as connection:
        if "diagnostics" not in column_names:
            # JSON is supported by PostgreSQL and accepted by SQLite, which
            # keeps the migration deterministic for the API contract tests.
            connection.execute(
                text("ALTER TABLE vectorizations ADD COLUMN diagnostics JSON")
            )

        # Earlier versions accepted duplicate idempotency keys. Retain the
        # oldest existing job as the historical replay target and clear later
        # duplicates before adding the unique index. This preserves every job
        # record while allowing new submissions to be race-safe.
        duplicate_keys = connection.execute(
            text(
                "SELECT idempotency_key FROM vectorizations "
                "WHERE idempotency_key IS NOT NULL "
                "GROUP BY idempotency_key HAVING COUNT(*) > 1"
            )
        ).scalars()
        for key in duplicate_keys:
            duplicate_ids = connection.execute(
                text(
                    "SELECT id FROM vectorizations "
                    "WHERE idempotency_key = :key "
                    "ORDER BY created_at ASC, id ASC"
                ),
                {"key": key},
            ).scalars()
            for duplicate_id in list(duplicate_ids)[1:]:
                connection.execute(
                    text(
                        "UPDATE vectorizations SET idempotency_key = NULL "
                        "WHERE id = :id"
                    ),
                    {"id": duplicate_id},
                )

        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "uq_vectorizations_idempotency_key "
                "ON vectorizations (idempotency_key)"
            )
        )
        columns = {column["name"] for column in inspector.get_columns("vectorizations")}
        if "batch_id" not in columns:
            connection.execute(
                text("ALTER TABLE vectorizations ADD COLUMN batch_id VARCHAR(36)")
            )
        if "batch_index" not in columns:
            connection.execute(
                text("ALTER TABLE vectorizations ADD COLUMN batch_index INTEGER")
            )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_vectorizations_batch_id ON vectorizations (batch_id)"
            )
        )

        if "vectorization_batches" in tables:
            batch_columns = {
                column["name"]
                for column in inspect(database_engine).get_columns(
                    "vectorization_batches"
                )
            }
            if "source_fingerprint" not in batch_columns:
                connection.execute(
                    text(
                        "ALTER TABLE vectorization_batches ADD COLUMN source_fingerprint VARCHAR(64)"
                    )
                )

    # Batch tables are additive and intentionally created for upgrades from
    # the single-image schema.  The ORM handles fresh installations.
    if "vectorization_batches" not in tables:
        from app.models import VectorizationBatch

        VectorizationBatch.__table__.create(bind=database_engine, checkfirst=True)
