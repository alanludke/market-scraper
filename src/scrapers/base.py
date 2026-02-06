"""
DEPRECATED: Use src.ingest.scrapers.base.BaseScraper instead.

This legacy BaseScraper lacks:
- Structured logging (uses stdlib logging instead of Loguru)
- Operational metrics tracking (no DuckDB metrics)
- Parquet output (only JSONL, 35x slower)
- Proper error handling (silent failures in subclasses)

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
import logging
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
from pathlib import Path
from typing import Optional


logger = logging.getLogger("market_scraper")


class BaseScraper:
    def __init__(self, store_name: str, config: dict):
        self.store_name = store_name
        self.base_url = config["base_url"].rstrip("/")
        self.regions = config["regions"]
        self.batch_size = config.get("batch_size", 50)
        self.request_delay = config.get("request_delay", 0.2)
        self.config = config

        self.run_timestamp = datetime.now()
        self.run_id = self.run_timestamp.strftime("%Y%m%d_%H%M%S")
        self.session = self._create_session()

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
        logger.info(f"[{self.store_name}] Starting run for {len(targets)} regions")

        product_ids = self.discover_products(limit)
        logger.info(f"[{self.store_name}] Discovered {len(product_ids)} products")

        for region_key in targets:
            if region_key not in self.regions:
                logger.warning(f"Region '{region_key}' not found in config, skipping")
                continue
            self.scrape_region(region_key, product_ids)
            self.session.cookies.clear()

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
        region_cfg = self.regions[region_key]
        with open(batch_file, "w", encoding="utf-8") as f:
            for item in items:
                item["_metadata"] = {
                    "supermarket": self.store_name,
                    "region": region_key,
                    "postal_code": region_cfg.get("cep"),
                    "hub_id": region_cfg.get("hub_id"),
                    "run_id": self.run_id,
                    "scraped_at": datetime.now().isoformat(),
                    **(extra_metadata or {}),
                }
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def consolidate_batches(self, batches_dir: Path, final_file: Path) -> int:
        count = 0
        with open(final_file, "w", encoding="utf-8") as out:
            for f in sorted(batches_dir.glob("*.jsonl")):
                with open(f, "r", encoding="utf-8") as inp:
                    content = inp.read()
                    out.write(content)
                    count += content.count("\n")
        logger.info(f"Consolidated {count} products -> {final_file.name}")
        return count

    def validate_run(self, region_key: str, file_path: Path, min_expected: int = 500):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                count = sum(1 for _ in f)
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
