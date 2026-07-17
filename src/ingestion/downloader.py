"""Fetch the UCI Online Retail dataset."""
from __future__ import annotations

from pathlib import Path

import requests

from src.common.logging_setup import get_logger
from src.config import settings

log = get_logger(__name__)

UCI_ONLINE_RETAIL_URL = (
    "https://archive.ics.uci.edu/ml/machine-learning-databases/00352/"
    "Online%20Retail.xlsx"
)


def download_online_retail(force: bool = False) -> tuple[Path, str]:
    """Download the dataset if not present. Returns (local_path, source_uri)."""
    raw_dir = settings.bronze_dir / "_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / "online_retail.xlsx"

    if target.exists() and not force:
        log.info("Dataset already present at %s (use force=True to redownload)", target)
        return target, UCI_ONLINE_RETAIL_URL

    log.info("Downloading %s", UCI_ONLINE_RETAIL_URL)
    with requests.get(UCI_ONLINE_RETAIL_URL, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with target.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                if chunk:
                    f.write(chunk)

    log.info("Saved to %s (%.2f MB)", target, target.stat().st_size / 1e6)
    return target, UCI_ONLINE_RETAIL_URL
