"""
Migrate legacy JSONL data to Parquet format with schema validation and data cleaning.

This script migrates data from archive/legacy_scrapers/ to the new data/bronze/ structure:
- Reads JSONL files from legacy scrapers
- Validates data against VTEXProduct schema (Pydantic)
- Deduplicates products by product_id + scraped_at
- Cleans and normalizes data (prices, EANs, etc.)
- Converts to Parquet with proper partitioning
- Follows the new naming convention: run_{store}_{timestamp}

Usage:
    python scripts/migrate_legacy_data.py --store bistek --dry-run
    python scripts/migrate_legacy_data.py --store all
    python scripts/migrate_legacy_data.py --store bistek --start-date 2026-01-25 --end-date 2026-01-30
"""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import pandas as pd
from loguru import logger
from pydantic import ValidationError
from tqdm import tqdm

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.schemas.vtex import VTEXProduct

# Configure logger
logger.add(
    "data/logs/migration_{time}.log",
    rotation="10 MB",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)


class LegacyDataMigrator:
    """Migrates legacy JSONL data to Parquet format."""

    def __init__(self, archive_path: Path, bronze_path: Path, dry_run: bool = False):
        self.archive_path = archive_path
        self.bronze_path = bronze_path
        self.dry_run = dry_run
        self.stats = {
            "files_processed": 0,
            "files_skipped": 0,
            "records_total": 0,
            "records_migrated": 0,
            "records_invalid": 0,
            "records_duplicated": 0,
            "errors": 0
        }

    def migrate_store(
        self,
        store: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> None:
        """Migrate all JSONL files for a specific store."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting migration for store: {store.upper()}")
        logger.info(f"{'='*60}")

        # Find legacy scraper directory
        legacy_dir = self.archive_path / f"legacy_scrapers/{store}_products_scraper/data/bronze/supermarket={store}"

        if not legacy_dir.exists():
            logger.error(f"Legacy directory not found: {legacy_dir}")
            return

        # Find all JSONL files
        jsonl_files = list(legacy_dir.glob("**/run_*/*.jsonl"))
        logger.info(f"Found {len(jsonl_files)} JSONL files for {store}")

        if start_date:
            logger.info(f"Filtering from: {start_date.strftime('%Y-%m-%d')}")
        if end_date:
            logger.info(f"Filtering until: {end_date.strftime('%Y-%m-%d')}")

        for jsonl_file in tqdm(jsonl_files, desc=f"Migrating {store}"):
            try:
                # Extract metadata from path
                # Path format: .../region=X/year=Y/month=M/day=D/run_YYYYMMDD_HHMMSS/file.jsonl
                parts = jsonl_file.parts
                region = parts[-6].replace("region=", "")
                year = parts[-5].replace("year=", "")
                month = parts[-4].replace("month=", "")
                day = parts[-3].replace("day=", "")
                run_id = parts[-2]  # run_YYYYMMDD_HHMMSS folder

                # Parse date for filtering
                file_date = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")

                # Apply date filters
                if start_date and file_date < start_date:
                    logger.debug(f"Skipping {jsonl_file} (before start_date)")
                    self.stats["files_skipped"] += 1
                    continue

                if end_date and file_date > end_date:
                    logger.debug(f"Skipping {jsonl_file} (after end_date)")
                    self.stats["files_skipped"] += 1
                    continue

                # Process file
                self._migrate_file(
                    jsonl_file=jsonl_file,
                    store=store,
                    region=region,
                    year=year,
                    month=month,
                    day=day,
                    run_id=run_id
                )

            except Exception as e:
                logger.error(f"Error processing {jsonl_file}: {e}")
                self.stats["errors"] += 1

        logger.info(f"Migration complete for {store}: {self.stats}")

    def _validate_and_clean_records(self, records: list[dict]) -> list[dict]:
        """Validate records against VTEXProduct schema and clean data."""
        valid_records = []

        for record in records:
            try:
                # Validate with Pydantic schema
                product = VTEXProduct.parse_obj(record)

                # Convert back to dict (normalized)
                clean_record = product.dict()
                valid_records.append(clean_record)

            except ValidationError as e:
                self.stats["records_invalid"] += 1
                logger.debug(f"Invalid record: {e}")
            except Exception as e:
                self.stats["records_invalid"] += 1
                logger.debug(f"Unexpected validation error: {e}")

        return valid_records

    def _migrate_file(
        self,
        jsonl_file: Path,
        store: str,
        region: str,
        year: str,
        month: str,
        day: str,
        run_id: str
    ) -> None:
        """Migrate a single JSONL file to Parquet with validation and cleaning."""
        logger.info(f"Processing: {jsonl_file.name}")

        # Read JSONL
        records = []
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line.strip()))
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON line in {jsonl_file}: {e}")
                    self.stats["records_invalid"] += 1

        if not records:
            logger.warning(f"No valid records found in {jsonl_file}")
            self.stats["files_skipped"] += 1
            return

        self.stats["records_total"] += len(records)
        logger.info(f"  Read {len(records)} records")

        # Validate and clean records with Pydantic schema
        logger.info(f"  Validating against VTEXProduct schema...")
        valid_records = self._validate_and_clean_records(records)

        if not valid_records:
            logger.warning(f"No valid records after validation in {jsonl_file}")
            self.stats["files_skipped"] += 1
            return

        logger.info(f"  Valid records: {len(valid_records)}/{len(records)}")

        # Convert to DataFrame
        df = pd.DataFrame(valid_records)

        # Remove duplicate columns if they exist
        if df.columns.duplicated().any():
            logger.warning(f"  Found duplicate columns: {df.columns[df.columns.duplicated()].tolist()}")
            df = df.loc[:, ~df.columns.duplicated()]

        # Add metadata columns
        if "scraped_at" in df.columns:
            df["scraped_at"] = pd.to_datetime(df["scraped_at"])
        else:
            df["scraped_at"] = datetime.now()

        df["_source_file"] = str(jsonl_file)
        df["_migrated_at"] = datetime.now()

        # Deduplicate by product_id + scraped_at
        initial_count = len(df)
        if "product_id" in df.columns:
            df = df.drop_duplicates(subset=["product_id", "scraped_at"], keep="first")
            duplicates_removed = initial_count - len(df)
        else:
            logger.warning(f"  No product_id column found, skipping deduplication")
            duplicates_removed = 0

        if duplicates_removed > 0:
            self.stats["records_duplicated"] += duplicates_removed
            logger.info(f"  Removed {duplicates_removed} duplicate records")

        # Create output path with new naming convention
        # Extract timestamp from run_id (format: run_20260125_161503)
        timestamp_str = run_id.replace("run_", "")
        new_run_id = f"run_{store}_{timestamp_str}"

        output_dir = (
            self.bronze_path /
            f"supermarket={store}" /
            f"region={region}" /
            f"year={year}" /
            f"month={month.zfill(2)}" /
            f"day={day.zfill(2)}"
        )

        output_file = output_dir / f"{new_run_id}.parquet"

        if self.dry_run:
            logger.info(f"  [DRY RUN] Would write {len(df)} records to: {output_file}")
            self.stats["records_migrated"] += len(df)
            self.stats["files_processed"] += 1
            return

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write Parquet with Snappy compression
        df.to_parquet(
            output_file,
            engine="pyarrow",
            compression="snappy",
            index=False
        )

        jsonl_size_mb = jsonl_file.stat().st_size / 1024 / 1024
        parquet_size_mb = output_file.stat().st_size / 1024 / 1024
        compression_ratio = (1 - parquet_size_mb / jsonl_size_mb) * 100 if jsonl_size_mb > 0 else 0

        logger.info(f"✓ Migrated {len(df)} records")
        logger.info(f"  Output: {output_file.relative_to(self.bronze_path)}")
        logger.info(f"  Size: {jsonl_size_mb:.2f} MB (JSONL) → {parquet_size_mb:.2f} MB (Parquet)")
        logger.info(f"  Compression: {compression_ratio:.1f}%")

        self.stats["records_migrated"] += len(df)
        self.stats["files_processed"] += 1

    def print_summary(self) -> None:
        """Print migration summary."""
        logger.info("\n" + "=" * 60)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Files processed: {self.stats['files_processed']}")
        logger.info(f"Files skipped: {self.stats['files_skipped']}")
        logger.info(f"Records total: {self.stats['records_total']:,}")
        logger.info(f"Records migrated: {self.stats['records_migrated']:,}")
        logger.info(f"Records invalid: {self.stats['records_invalid']:,}")
        logger.info(f"Records duplicated: {self.stats['records_duplicated']:,}")
        logger.info(f"Errors: {self.stats['errors']}")

        # Calculate success rate
        if self.stats['records_total'] > 0:
            success_rate = (self.stats['records_migrated'] / self.stats['records_total']) * 100
            logger.info(f"Success rate: {success_rate:.1f}%")

        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Migrate legacy JSONL data to Parquet")
    parser.add_argument(
        "--store",
        required=True,
        choices=["bistek", "fort", "giassi", "all"],
        help="Store to migrate (or 'all' for all stores)"
    )
    parser.add_argument(
        "--start-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        help="Start date (YYYY-MM-DD) - only migrate files from this date onwards"
    )
    parser.add_argument(
        "--end-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        help="End date (YYYY-MM-DD) - only migrate files up to this date"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run - don't actually write files"
    )

    args = parser.parse_args()

    # Initialize migrator
    archive_path = Path("archive")
    bronze_path = Path("data/bronze")

    migrator = LegacyDataMigrator(
        archive_path=archive_path,
        bronze_path=bronze_path,
        dry_run=args.dry_run
    )

    # Migrate stores
    stores = ["bistek", "fort", "giassi"] if args.store == "all" else [args.store]

    for store in stores:
        migrator.migrate_store(
            store=store,
            start_date=args.start_date,
            end_date=args.end_date
        )

    # Print summary
    migrator.print_summary()

    if args.dry_run:
        logger.info("\nℹ️  This was a DRY RUN - no files were actually written")
        logger.info("Run without --dry-run to perform the actual migration")


if __name__ == "__main__":
    main()