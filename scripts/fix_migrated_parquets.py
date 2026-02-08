"""
Fix migrated Parquet files by adding missing _metadata_* columns.

This script updates Parquet files that were migrated from legacy JSONL format
to match the current scraper schema by adding the required metadata columns.

Usage:
    python scripts/fix_migrated_parquets.py --dry-run  # Test without writing
    python scripts/fix_migrated_parquets.py            # Actually fix files
"""

import argparse
from pathlib import Path
import pandas as pd
from loguru import logger
from tqdm import tqdm

# Configure logger
logger.add(
    "data/logs/fix_parquets_{time}.log",
    rotation="10 MB",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)


def fix_migrated_parquets(bronze_path: Path, dry_run: bool = False):
    """Fix migrated Parquet files by adding _metadata_* columns."""

    stats = {
        "files_checked": 0,
        "files_fixed": 0,
        "files_skipped": 0,
        "errors": 0
    }

    # Find ALL Parquet files that need fixing
    parquet_files = list(bronze_path.glob("**/*.parquet"))
    logger.info(f"Found {len(parquet_files)} total Parquet files")

    for parquet_file in tqdm(parquet_files, desc="Fixing Parquet files"):
        try:
            stats["files_checked"] += 1

            # Read Parquet file
            df = pd.read_parquet(parquet_file)

            # Check if already has metadata columns
            if "_metadata_scraped_at" in df.columns:
                logger.debug(f"Skipping {parquet_file.name} (already has metadata)")
                stats["files_skipped"] += 1
                continue

            # Extract metadata from file path
            # Path format: .../supermarket=X/region=Y/year=Z/month=M/day=D/run_store_YYYYMMDD_HHMMSS.parquet
            parts = parquet_file.parts

            supermarket = None
            region = None
            for part in parts:
                if part.startswith("supermarket="):
                    supermarket = part.replace("supermarket=", "")
                elif part.startswith("region="):
                    region = part.replace("region=", "")

            if not supermarket or not region:
                logger.warning(f"Could not extract metadata from path: {parquet_file}")
                stats["errors"] += 1
                continue

            # Add missing metadata columns
            df["_metadata_supermarket"] = supermarket
            df["_metadata_region"] = region
            df["_metadata_run_id"] = parquet_file.stem  # run_bistek_20260125_161503

            # Copy scraped_at to _metadata_scraped_at
            if "scraped_at" in df.columns:
                df["_metadata_scraped_at"] = pd.to_datetime(df["scraped_at"])
            else:
                logger.warning(f"No scraped_at column in {parquet_file.name}")
                df["_metadata_scraped_at"] = pd.Timestamp.now()

            # Set optional metadata to None (legacy data doesn't have these)
            df["_metadata_postal_code"] = None
            df["_metadata_hub_id"] = None

            if dry_run:
                logger.info(f"[DRY RUN] Would fix {parquet_file.name}")
                logger.debug(f"  Would add: _metadata_supermarket={supermarket}, _metadata_region={region}")
                stats["files_fixed"] += 1
            else:
                # Overwrite the file with updated schema
                df.to_parquet(
                    parquet_file,
                    engine="pyarrow",
                    compression="snappy",
                    index=False
                )
                logger.info(f"✓ Fixed {parquet_file.name}")
                stats["files_fixed"] += 1

        except Exception as e:
            logger.error(f"Error processing {parquet_file}: {e}")
            stats["errors"] += 1

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("PARQUET FIX SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Files checked: {stats['files_checked']}")
    logger.info(f"Files fixed: {stats['files_fixed']}")
    logger.info(f"Files skipped: {stats['files_skipped']} (already had metadata)")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("=" * 60)

    if dry_run:
        logger.info("\nℹ️  This was a DRY RUN - no files were actually modified")
        logger.info("Run without --dry-run to apply the fixes")


def main():
    parser = argparse.ArgumentParser(description="Fix migrated Parquet files")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run - don't actually modify files"
    )

    args = parser.parse_args()

    bronze_path = Path("data/bronze")

    if not bronze_path.exists():
        logger.error(f"Bronze directory not found: {bronze_path}")
        return

    fix_migrated_parquets(bronze_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
