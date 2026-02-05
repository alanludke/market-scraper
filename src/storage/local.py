"""Local filesystem storage utilities for bronze layer."""

import shutil
import logging
from pathlib import Path

logger = logging.getLogger("market_scraper")


def cleanup_batches(run_dir: Path):
    """Remove batch files after consolidation to save disk space."""
    batches_dir = run_dir / "batches"
    if batches_dir.exists():
        shutil.rmtree(batches_dir)
        logger.info(f"Cleaned up batches in {run_dir}")


def get_data_size(path: Path = Path("data")) -> str:
    """Return total size of data directory as human-readable string."""
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    for unit in ["B", "KB", "MB", "GB"]:
        if total < 1024:
            return f"{total:.1f} {unit}"
        total /= 1024
    return f"{total:.1f} TB"
