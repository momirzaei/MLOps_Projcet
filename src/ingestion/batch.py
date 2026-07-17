"""Batch identity, file hashing, and audit-table writes."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

from src.config import settings


def new_batch_id(source_name: str) -> str:
    """UTC-timestamped batch id: e.g. 20260717T143205Z-online_retail-3f2a1b7c."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{ts}-{source_name}-{uuid.uuid4().hex[:8]}"


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _engine():
    # audit table is owned by retail_owner
    return create_engine(settings.owner_url, future=True)


def record_batch_start(
    *,
    batch_id: str,
    source_name: str,
    source_uri: str,
    file_path: Path,
    file_sha256: str,
) -> None:
    with _engine().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO audit.ingestion_batches (
                    batch_id, source_name, source_uri, file_name,
                    file_sha256, file_size_bytes,
                    ingest_started_at, status
                ) VALUES (
                    :batch_id, :source_name, :source_uri, :file_name,
                    :file_sha256, :file_size_bytes,
                    :started_at, 'running'
                )
                """
            ),
            {
                "batch_id": batch_id,
                "source_name": source_name,
                "source_uri": source_uri,
                "file_name": file_path.name,
                "file_sha256": file_sha256,
                "file_size_bytes": file_path.stat().st_size,
                "started_at": datetime.now(timezone.utc),
            },
        )


def record_batch_success(*, batch_id: str, row_count: int, bronze_path: str) -> None:
    with _engine().begin() as conn:
        conn.execute(
            text(
                """
                UPDATE audit.ingestion_batches
                SET status = 'success',
                    row_count = :row_count,
                    bronze_path = :bronze_path,
                    ingest_finished_at = :finished_at
                WHERE batch_id = :batch_id
                """
            ),
            {
                "batch_id": batch_id,
                "row_count": row_count,
                "bronze_path": bronze_path,
                "finished_at": datetime.now(timezone.utc),
            },
        )


def record_batch_failure(*, batch_id: str, error_message: str) -> None:
    with _engine().begin() as conn:
        conn.execute(
            text(
                """
                UPDATE audit.ingestion_batches
                SET status = 'failed',
                    error_message = :error_message,
                    ingest_finished_at = :finished_at
                WHERE batch_id = :batch_id
                """
            ),
            {
                "batch_id": batch_id,
                "error_message": error_message[:2000],
                "finished_at": datetime.now(timezone.utc),
            },
        )
