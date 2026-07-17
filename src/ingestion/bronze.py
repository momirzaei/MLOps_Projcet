"""Bronze ingestion: raw file -> Parquet with ingestion metadata."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType

from src.common.logging_setup import get_logger
from src.common.spark import build_spark
from src.config import settings
from src.ingestion.batch import (
    new_batch_id,
    record_batch_failure,
    record_batch_start,
    record_batch_success,
    sha256_of_file,
)
from src.ingestion.downloader import download_online_retail

log = get_logger(__name__)

SOURCE_NAME = "online_retail"


def _read_xlsx_to_spark(spark: SparkSession, xlsx_path: Path) -> DataFrame:
    """Read xlsx via pandas, then hand off to Spark.

    Bronze keeps all source columns as strings; typing happens in Silver.
    """
    log.info("Reading xlsx into pandas: %s", xlsx_path)
    pdf = pd.read_excel(xlsx_path, dtype=str, engine="openpyxl")
    pdf.columns = [c.strip() for c in pdf.columns]
    log.info("Rows read: %d, columns: %s", len(pdf), list(pdf.columns))
    sdf = spark.createDataFrame(pdf)
    for c in sdf.columns:
        sdf = sdf.withColumn(c, sdf[c].cast(StringType()))
    return sdf


def run_bronze_ingest(force_download: bool = False) -> dict:
    """Full Bronze run. Returns a summary dict."""
    xlsx_path, source_uri = download_online_retail(force=force_download)
    file_hash = sha256_of_file(xlsx_path)
    batch_id = new_batch_id(SOURCE_NAME)
    ingest_ts = datetime.now(timezone.utc)

    log.info("Batch %s starting (sha256=%s)", batch_id, file_hash[:12])
    record_batch_start(
        batch_id=batch_id,
        source_name=SOURCE_NAME,
        source_uri=source_uri,
        file_path=xlsx_path,
        file_sha256=file_hash,
    )

    spark: SparkSession | None = None
    try:
        spark = build_spark("bronze-ingest")
        sdf = _read_xlsx_to_spark(spark, xlsx_path)

        # Ingestion metadata for Bronze lineage.
        sdf_with_meta = (
            sdf
            .withColumn("_batch_id", F.lit(batch_id))
            .withColumn("_source_name", F.lit(SOURCE_NAME))
            .withColumn("_source_uri", F.lit(source_uri))
            .withColumn("_source_file", F.lit(xlsx_path.name))
            .withColumn("_source_sha256", F.lit(file_hash))
            .withColumn("_ingest_ts_utc", F.lit(ingest_ts))
            .withColumn("_ingest_date", F.lit(ingest_ts.date().isoformat()))
        )

        row_count = sdf_with_meta.count()
        out_path = settings.bronze_dir / SOURCE_NAME
        out_path.mkdir(parents=True, exist_ok=True)

        log.info("Writing %d rows to %s", row_count, out_path)
        (
            sdf_with_meta.write
            .mode("append")
            .partitionBy("_ingest_date")
            .parquet(str(out_path))
        )

        record_batch_success(
            batch_id=batch_id,
            row_count=row_count,
            bronze_path=str(out_path),
        )
        log.info("Batch %s success: %d rows written", batch_id, row_count)
        return {
            "batch_id": batch_id,
            "row_count": row_count,
            "bronze_path": str(out_path),
            "file_sha256": file_hash,
        }

    except Exception as exc:
        log.exception("Batch %s failed", batch_id)
        record_batch_failure(batch_id=batch_id, error_message=repr(exc))
        raise
    finally:
        if spark is not None:
            spark.stop()
