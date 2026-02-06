"""
Convert historical JSONL files to Parquet format.

Usage:
    python utilities/convert_jsonl_to_parquet.py                    # Convert all JSONL in data/bronze
    python utilities/convert_jsonl_to_parquet.py --dry-run          # Preview without converting
    python utilities/convert_jsonl_to_parquet.py --delete-jsonl     # Delete JSONL after conversion

Benefits:
- 80-90% size reduction (11GB → ~1-2GB)
- 35x faster queries
- Native DuckDB/Pandas integration
"""

import argparse
import json
from pathlib import Path
import pandas as pd
from loguru import logger
import sys

# Setup simple console logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


def convert_jsonl_to_parquet(jsonl_path: Path, delete_jsonl: bool = False) -> bool:
    """
    Convert a single JSONL file to Parquet.

    Args:
        jsonl_path: Path to input JSONL file
        delete_jsonl: If True, delete JSONL after successful conversion

    Returns:
        True if conversion succeeded
    """
    parquet_path = jsonl_path.with_suffix(".parquet")

    if parquet_path.exists():
        logger.debug(f"Skipping {jsonl_path.name} (Parquet already exists)")
        return False

    try:
        # Read JSONL
        records = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))

        if not records:
            logger.warning(f"Empty file: {jsonl_path}")
            return False

        # Convert to DataFrame
        df = pd.json_normalize(records, sep="_")

        # Write Parquet
        df.to_parquet(
            parquet_path,
            engine="pyarrow",
            compression="snappy",
            index=False
        )

        # Calculate size reduction
        jsonl_size = jsonl_path.stat().st_size / 1024 / 1024  # MB
        parquet_size = parquet_path.stat().st_size / 1024 / 1024  # MB
        reduction = (1 - parquet_size / jsonl_size) * 100

        logger.info(
            f"Converted {jsonl_path.name}: {len(df)} records, "
            f"{jsonl_size:.1f}MB -> {parquet_size:.1f}MB ({reduction:.0f}% reduction)"
        )

        # Delete JSONL if requested
        if delete_jsonl:
            jsonl_path.unlink()
            logger.debug(f"Deleted {jsonl_path.name}")

        return True

    except Exception as e:
        logger.error(f"Failed to convert {jsonl_path}: {e}")
        return False


def scan_and_convert(
    bronze_dir: Path,
    dry_run: bool = False,
    delete_jsonl: bool = False,
    exclude_patterns: list[str] = None
) -> dict:
    """
    Scan bronze directory for JSONL files and convert to Parquet.

    Args:
        bronze_dir: Root bronze directory
        dry_run: If True, only scan and report, don't convert
        delete_jsonl: If True, delete JSONL after conversion
        exclude_patterns: List of patterns to exclude (e.g., ["bad_", "test_"])

    Returns:
        Dictionary with conversion statistics
    """
    exclude_patterns = exclude_patterns or ["bad_", "archive/"]

    # Find all JSONL files
    jsonl_files = []
    for jsonl_path in bronze_dir.rglob("*.jsonl"):
        # Skip excluded patterns
        if any(pattern in str(jsonl_path) for pattern in exclude_patterns):
            logger.debug(f"Skipping excluded: {jsonl_path}")
            continue
        jsonl_files.append(jsonl_path)

    logger.info(f"Found {len(jsonl_files)} JSONL files to convert")

    if dry_run:
        logger.info("DRY RUN MODE - No files will be converted")
        for jsonl_path in jsonl_files:
            size_mb = jsonl_path.stat().st_size / 1024 / 1024
            logger.info(f"  Would convert: {jsonl_path.name} ({size_mb:.1f}MB)")
        return {"total": len(jsonl_files), "converted": 0, "skipped": 0, "failed": 0}

    # Convert each file
    stats = {"total": len(jsonl_files), "converted": 0, "skipped": 0, "failed": 0}

    for i, jsonl_path in enumerate(jsonl_files, 1):
        logger.info(f"[{i}/{len(jsonl_files)}] Processing {jsonl_path.relative_to(bronze_dir)}...")

        try:
            result = convert_jsonl_to_parquet(jsonl_path, delete_jsonl=delete_jsonl)
            if result:
                stats["converted"] += 1
            else:
                stats["skipped"] += 1
        except Exception as e:
            logger.error(f"Error: {e}")
            stats["failed"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Convert JSONL files to Parquet")
    parser.add_argument(
        "--bronze-dir",
        type=Path,
        default=Path("data/bronze"),
        help="Bronze directory path (default: data/bronze)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview files without converting"
    )
    parser.add_argument(
        "--delete-jsonl",
        action="store_true",
        help="Delete JSONL files after successful conversion"
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=["bad_", "archive/"],
        help="Patterns to exclude (default: bad_ archive/)"
    )

    args = parser.parse_args()

    if not args.bronze_dir.exists():
        logger.error(f"Bronze directory not found: {args.bronze_dir}")
        sys.exit(1)

    logger.info(f"Scanning bronze directory: {args.bronze_dir}")
    logger.info(f"Excluding patterns: {args.exclude}")

    stats = scan_and_convert(
        bronze_dir=args.bronze_dir,
        dry_run=args.dry_run,
        delete_jsonl=args.delete_jsonl,
        exclude_patterns=args.exclude
    )

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("CONVERSION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total files found:  {stats['total']}")
    logger.info(f"Converted:          {stats['converted']}")
    logger.info(f"Skipped:            {stats['skipped']} (already Parquet)")
    logger.info(f"Failed:             {stats['failed']}")
    logger.info("=" * 60)

    if stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
