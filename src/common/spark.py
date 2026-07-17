"""SparkSession factory tuned for local Bronze/Silver processing.

Windows self-contained mode: on first run, downloads winutils.exe + hadoop.dll
into <project>/tools/hadoop/bin/ and points HADOOP_HOME there. Zero manual setup
for developers cloning the repo. No-op on Linux/macOS.
"""
from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

from pyspark.sql import SparkSession

from src.common.logging_setup import get_logger
from src.config import PROJECT_ROOT

log = get_logger(__name__)

# Hadoop 3.3.6 pairs with Spark 3.5.x.
_WINUTILS_BASE = "https://github.com/cdarlint/winutils/raw/master/hadoop-3.3.6/bin"

# Minimum expected file sizes; catches "downloaded HTML page" failures.
_REQUIRED_FILES = {
    "winutils.exe": 50_000,
    "hadoop.dll": 500_000,
}


def _ensure_hadoop_home_windows() -> None:
    """Ensure Windows has valid project-local winutils.exe and hadoop.dll."""
    if sys.platform != "win32":
        return

    hadoop_home = PROJECT_ROOT / "tools" / "hadoop"
    bin_dir = hadoop_home / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    for fname, min_size in _REQUIRED_FILES.items():
        target = bin_dir / fname
        if target.exists() and target.stat().st_size >= min_size:
            continue

        url = f"{_WINUTILS_BASE}/{fname}"
        log.info("First-time setup: downloading %s", fname)
        try:
            urllib.request.urlretrieve(url, target)
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise RuntimeError(
                f"Failed to download {fname} from {url}: {exc}. "
                "Check your internet connection and retry."
            ) from exc

        size = target.stat().st_size
        if size < min_size:
            target.unlink(missing_ok=True)
            raise RuntimeError(
                f"Downloaded {fname} is only {size} bytes "
                f"(expected >= {min_size}). The URL likely returned an HTML "
                f"page instead of the binary. Retry, or download manually "
                f"from {url} into {bin_dir}."
            )
        log.info("  saved %s (%.1f KB)", target.name, size / 1024)

    os.environ["HADOOP_HOME"] = str(hadoop_home)
    os.environ["hadoop.home.dir"] = str(hadoop_home)
    bin_str = str(bin_dir)
    if bin_str not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = bin_str + os.pathsep + os.environ.get("PATH", "")


def build_spark(app_name: str = "retail-bi") -> SparkSession:
    _ensure_hadoop_home_windows()
    return (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )
