"""
Base scraper class. All platform-specific scrapers inherit from this.

BaseScraper handles:
- HTTP session with retry logic
- Bronze layer storage (local JSONL)
- Metadata injection per product
- Batch file consolidation
- Run validation

To add a new (non-VTEX) supermarket, subclass BaseScraper and implement:
- discover_products(limit) -> list of product identifiers
- scrape_region(region_key, product_ids) -> saves JSONL to bronze layer
"""

import json
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger

from src.observability.metrics import get_metrics_collector
from src.observability.logging_config import setup_logging
from src.ingest.loaders.parquet_writer import write_parquet, consolidate_parquet_files


class BaseScraper:
    def __init__(self, store_name: str, config: dict):
        self.store_name = store_name
        self.base_url = config["base_url"].rstrip("/")
        self.regions = config["regions"]
        self.batch_size = config.get("batch_size", 50)
        self.request_delay = config.get("request_delay", 0.2)
        self.config = config

        self.run_timestamp = datetime.now()
        # Include store name to ensure unique run_id in parallel execution
        self.run_id = f"{store_name}_{self.run_timestamp.strftime('%Y%m%d_%H%M%S')}"
        self.session = self._create_session()

        # Setup logging with run context (reconfigure globally)
        setup_logging(run_id=self.run_id, store=store_name, region="all", verbose=False)

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        return session

    # -- Override in subclasses --

    def discover_products(self, limit: Optional[int] = None) -> list[str]:
        raise NotImplementedError

    def scrape_region(self, region_key: str, product_ids: list[str]):
        raise NotImplementedError

    # -- Shared infrastructure --

    def run(self, regions: list[str] | None = None, limit: Optional[int] = None):
        """Main entry point. Override if the scraper needs a different flow."""
        targets = regions or list(self.regions.keys())
        metrics = get_metrics_collector()

        # Start metrics tracking (single run for all regions)
        metrics.start_run(self.run_id, self.store_name, region="all")
        logger.info(f"[{self.store_name}] Starting run {self.run_id} for {len(targets)} regions")

        try:
            product_ids = self.discover_products(limit)
            logger.info(f"[{self.store_name}] Discovered {len(product_ids)} products")

            for region_key in targets:
                if region_key not in self.regions:
                    logger.warning(f"Region '{region_key}' not found in config, skipping")
                    continue
                self.scrape_region(region_key, product_ids)
                self.session.cookies.clear()

            # Success: finish run with metrics
            metrics.finish_run(
                status="success",
                products_discovered=len(product_ids),
                products_scraped=len(product_ids) * len(targets)
            )
            logger.info(f"[{self.store_name}] Run {self.run_id} completed successfully")

        except Exception as e:
            # Failure: log and record error
            logger.exception(f"[{self.store_name}] Run {self.run_id} failed")
            metrics.finish_run(
                status="failed",
                error_message=str(e)
            )
            raise

    def get_output_path(self, region_key: str) -> Path:
        ts = self.run_timestamp
        return Path(
            f"data/bronze/supermarket={self.store_name}/"
            f"region={region_key}/"
            f"year={ts.year}/month={ts.month:02d}/day={ts.day:02d}/"
            f"run_{self.run_id}"
        )

    def save_batch(
        self,
        items: list[dict],
        batch_file: Path,
        region_key: str,
        extra_metadata: dict | None = None,
    ):
        """
        Save batch to Parquet file with metadata injection.

        Changed from JSONL to Parquet for:
        - 80-90% size reduction (Snappy compression)
        - 35x faster queries (columnar format)
        - Native DuckDB/Pandas integration
        """
        region_cfg = self.regions[region_key]

        # Build metadata dict
        metadata = {
            "supermarket": self.store_name,
            "region": region_key,
            "postal_code": region_cfg.get("cep"),
            "hub_id": region_cfg.get("hub_id"),
            "run_id": self.run_id,
            "scraped_at": datetime.now().isoformat(),
            **(extra_metadata or {}),
        }

        # Convert batch_file extension from .jsonl to .parquet
        parquet_file = batch_file.with_suffix(".parquet")

        # Write to Parquet
        write_parquet(items, parquet_file, metadata=metadata)

    def consolidate_batches(self, batches_dir: Path, final_file: Path) -> int:
        """
        Consolidate batch Parquet files into a single file.

        Changed from JSONL to Parquet consolidation.
        """
        # Convert final_file extension from .jsonl to .parquet
        parquet_file = final_file.with_suffix(".parquet")

        # Consolidate all batch Parquet files
        count = consolidate_parquet_files(
            input_dir=batches_dir,
            output_file=parquet_file,
            pattern="*.parquet"
        )

        return count

    def validate_run(self, region_key: str, file_path: Path, min_expected: int = 500):
        """
        Validate run output by checking record count.

        Changed to read Parquet files instead of JSONL.
        """
        try:
            # Convert file_path extension from .jsonl to .parquet
            parquet_file = file_path.with_suffix(".parquet")

            # Read Parquet to get count (only metadata, fast)
            import pandas as pd
            df = pd.read_parquet(parquet_file, engine="pyarrow")
            count = len(df)

            if count < min_expected:
                logger.warning(
                    f"[{self.store_name}/{region_key}] LOW VOLUME: {count} items "
                    f"(expected >= {min_expected})"
                )
            else:
                logger.info(f"[{self.store_name}/{region_key}] OK: {count} items")
            return count
        except FileNotFoundError:
            logger.error(f"[{self.store_name}/{region_key}] Output file not found")
            return 0
