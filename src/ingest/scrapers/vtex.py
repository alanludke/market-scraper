"""
VTEX Commerce Cloud scraper.

Handles all VTEX-based supermarkets (Bistek, Fort, Giassi, Angeloni, etc.)
with two product discovery strategies:
  - sitemap: Parse sitemap XMLs for product IDs (Bistek)
  - category_tree: Walk department categories via API (Fort, Giassi)

And two scraping modes:
  - global_discovery=true: Discover all product IDs once, then batch-fetch per region
  - global_discovery=false: Iterate departments per region (Giassi-style)
"""

import json
import re
import time
import base64
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger
from pydantic import ValidationError

from .base import BaseScraper
from .rate_limiter import get_rate_limiter
from src.observability.metrics import get_metrics_collector
from src.schemas.vtex import VTEXProduct


class SitemapNotAvailableError(Exception):
    """Raised when sitemap discovery fails (404, parse error, etc)."""
    pass


class RegionResolver:
    """Builds VTEX segment cookies that control region-specific pricing."""

    def __init__(self, session, base_url: str):
        self.session = session
        self.base_url = base_url

    def get_segment_cookie(
        self,
        postal_code: str,
        sales_channel: str = "1",
        manual_region_id: str | None = None,
    ) -> str | None:
        region_id = manual_region_id

        if not region_id:
            clean_zip = postal_code.replace("-", "")
            url = (
                f"{self.base_url}/api/checkout/pub/regions"
                f"?country=BRA&postalCode={clean_zip}&sc={sales_channel}"
            )
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and data:
                        region_id = data[0].get("id")
                        if not region_id and "sellers" in data[0]:
                            for s in data[0]["sellers"]:
                                if s.get("id"):
                                    region_id = s["id"]
                                    break
            except Exception as e:
                logger.debug(f"Failed to fetch region ID for CEP {postal_code}: {e}")

        if not region_id:
            logger.warning(f"No region ID found for CEP {postal_code}")

        payload = {
            "campaigns": None,
            "channel": sales_channel,
            "priceTables": None,
            "regionId": region_id,
            "currencyCode": "BRL",
            "currencySymbol": "R$",
            "countryCode": "BRA",
            "cultureInfo": "pt-BR",
            "channelPrivacy": "public",
        }
        return base64.b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).decode()


class VTEXScraper(BaseScraper):
    def __init__(self, store_name: str, config: dict):
        super().__init__(store_name, config)
        self.resolver = RegionResolver(self.session, self.base_url)
        self.discovery = config.get("discovery", "category_tree")
        self.global_discovery = config.get("global_discovery", True)
        self.cookie_domain = config.get("cookie_domain", "")
        self.validation_errors_count = 0  # Track validation failures

        # Performance optimization (Phase 3)
        self.max_workers = config.get("max_workers", 1)  # Parallel regions
        self.rate_limiter = get_rate_limiter()  # Global VTEX rate limiter

    # ── Data Quality (Phase 2) ──────────────────────────────────

    def validate_products(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate products using Pydantic schemas.

        Invalid products are logged and skipped, preventing corrupted data
        from reaching the bronze layer.

        Args:
            products: List of product dictionaries from VTEX API

        Returns:
            List of validated product dictionaries (invalid products removed)
        """
        validated = []

        for product in products:
            try:
                # Validate using Pydantic
                validated_product = VTEXProduct.parse_obj(product)
                # Convert back to dict for downstream processing
                validated.append(validated_product.dict())
            except ValidationError as e:
                # Log validation error with context
                product_id = product.get('productId', 'unknown')
                product_name = product.get('productName', 'unknown')

                logger.warning(
                    f"Product validation failed: {product_id} - {product_name}",
                    extra={
                        "product_id": product_id,
                        "validation_errors": e.errors(),
                        "store": self.store_name,
                        "run_id": self.run_id
                    }
                )

                self.validation_errors_count += 1
                # Skip invalid product
                continue
            except Exception as e:
                # Unexpected error during validation
                logger.error(
                    f"Unexpected error validating product: {e}",
                    extra={
                        "product": product.get('productId', 'unknown'),
                        "store": self.store_name,
                        "run_id": self.run_id
                    }
                )
                self.validation_errors_count += 1
                continue

        # Log summary if any products were invalid
        if len(validated) < len(products):
            skipped = len(products) - len(validated)
            logger.info(
                f"Validation complete: {len(validated)}/{len(products)} products valid "
                f"({skipped} skipped due to validation errors)"
            )

        return validated

    # ── Entry point ─────────────────────────────────────────────

    def run(self, regions: list[str] | None = None, limit: Optional[int] = None):
        targets = regions or list(self.regions.keys())
        # Use per-store database for parallel execution (avoids file locking)
        metrics = get_metrics_collector(
            db_path="data/metrics/{store}_runs.duckdb",
            store_name=self.store_name
        )

        # Start metrics tracking
        metrics.start_run(self.run_id, self.store_name, region="all")
        logger.info(f"[{self.store_name}] Starting run {self.run_id} for {len(targets)} regions")

        try:
            if self.global_discovery:
                # Track discovery phase separately (Phase 1 enhancement)
                metrics.start_discovery(discovery_mode=self.discovery)
                product_ids = self.discover_products(limit)
                metrics.finish_discovery(products_discovered=len(product_ids))
                logger.info(f"[{self.store_name}] Discovered {len(product_ids)} products")

                # Phase 3 optimization: Parallel region scraping
                if self.max_workers > 1:
                    logger.info(f"[{self.store_name}] Scraping {len(targets)} regions in parallel (max_workers={self.max_workers})")
                    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                        # Submit all regions to thread pool
                        futures = {}
                        for region_key in targets:
                            if region_key not in self.regions:
                                logger.warning(f"Region '{region_key}' not in config, skipping")
                                continue
                            future = executor.submit(self._scrape_by_ids_parallel, region_key, product_ids)
                            futures[future] = region_key

                        # Wait for all regions to complete
                        for future in as_completed(futures):
                            region_key = futures[future]
                            try:
                                future.result()  # Raises exception if scraping failed
                                logger.info(f"[{self.store_name}/{region_key}] Completed")
                            except Exception as e:
                                logger.error(f"[{self.store_name}/{region_key}] Failed: {e}")
                else:
                    # Sequential mode (backward compatible)
                    for region_key in targets:
                        if region_key not in self.regions:
                            logger.warning(f"Region '{region_key}' not in config, skipping")
                            continue
                        self._scrape_by_ids(region_key, product_ids)
                        self.session.cookies.clear()

                # Success
                metrics.finish_run(
                    status="success",
                    products_discovered=len(product_ids),
                    products_scraped=len(product_ids) * len(targets),
                    validation_errors_count=self.validation_errors_count
                )
            else:
                for region_key in targets:
                    if region_key not in self.regions:
                        logger.warning(f"Region '{region_key}' not in config, skipping")
                        continue
                    self._scrape_by_departments(region_key, limit)
                    self.session.cookies.clear()

                # Success (per-region mode)
                metrics.finish_run(
                    status="success",
                    validation_errors_count=self.validation_errors_count
                )

            logger.info(f"[{self.store_name}] Run {self.run_id} completed successfully")

        except Exception as e:
            logger.exception(f"[{self.store_name}] Run {self.run_id} failed")
            metrics.finish_run(
                status="failed",
                error_message=str(e),
                validation_errors_count=self.validation_errors_count
            )
            raise

    # ── Discovery ───────────────────────────────────────────────

    def discover_products(self, limit: Optional[int] = None) -> list[str]:
        """
        Discover product IDs using configured strategy.

        Strategy:
        - If config specifies "category_tree": Use only category_tree (reliable for stores with stale sitemaps)
        - If config specifies "sitemap" or unspecified: Try sitemap first (fast path), fallback to category_tree if it fails

        This ensures stores with known stale sitemaps (Fort, Giassi) skip sitemap entirely.
        """
        discovery_method = self.config.get("discovery", "sitemap")

        # If config explicitly says category_tree, skip sitemap (e.g., Fort/Giassi have stale sitemaps)
        if discovery_method == "category_tree":
            logger.info(f"[{self.store_name}] Using category_tree discovery (config: discovery=category_tree)")
            product_ids = self._discover_via_categories(limit)
            logger.info(
                f"[{self.store_name}] Category tree discovery successful: {len(product_ids)} products",
                extra={"discovery_method": "category_tree", "products_count": len(product_ids)}
            )
            return product_ids

        # Otherwise, try sitemap first (fast path), fallback to category_tree if needed
        try:
            logger.info(f"[{self.store_name}] Attempting sitemap discovery (fast path)")
            product_ids = self._discover_via_sitemap(limit)
            logger.info(
                f"[{self.store_name}] Sitemap discovery successful: {len(product_ids)} products",
                extra={"discovery_method": "sitemap", "products_count": len(product_ids)}
            )
            return product_ids
        except SitemapNotAvailableError as e:
            # Sitemap not available - fallback to category_tree
            logger.warning(
                f"[{self.store_name}] Sitemap not available ({e}), falling back to category_tree",
                extra={"discovery_method": "category_tree_fallback", "sitemap_error": str(e)}
            )
            product_ids = self._discover_via_categories(limit)
            logger.info(
                f"[{self.store_name}] Category tree discovery successful: {len(product_ids)} products",
                extra={"discovery_method": "category_tree", "products_count": len(product_ids)}
            )
            return product_ids
        except Exception as e:
            # Unexpected error in sitemap - log and try category_tree
            logger.error(
                f"[{self.store_name}] Unexpected error in sitemap discovery: {e}, trying category_tree",
                extra={"discovery_method": "category_tree_fallback", "error": str(e)}
            )
            # Try category_tree as last resort
            return self._discover_via_categories(limit)

    def _discover_via_sitemap(self, limit: Optional[int] = None) -> list[str]:
        """
        Discover product IDs via sitemap XML files.

        Raises:
            SitemapNotAvailableError: If sitemap doesn't exist or returns no products
        """
        logger.info(f"[{self.store_name}] Discovering via sitemap...")
        self.session.cookies.clear()
        discovered = set()
        idx = 0
        pattern = self.config.get("sitemap_pattern", "/sitemap/product-{n}.xml")

        while True:
            url = f"{self.base_url}{pattern.replace('{n}', str(idx))}"
            try:
                resp = self.session.get(url, timeout=20)

                if resp.status_code != 200:
                    # If first sitemap returns non-200, sitemap doesn't exist
                    if idx == 0:
                        raise SitemapNotAvailableError(
                            f"Sitemap not found: {url} returned {resp.status_code}"
                        )
                    # Otherwise, we've reached the end of sitemaps (normal)
                    break

                root = ET.fromstring(resp.content)
                ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                count_before = len(discovered)
                for loc in root.findall(".//s:loc", ns):
                    match = re.search(r"-(\d+)/p", loc.text)
                    if match:
                        discovered.add(match.group(1))
                logger.info(
                    f"  sitemap-{idx}: +{len(discovered) - count_before} "
                    f"(total: {len(discovered)})"
                )
                idx += 1
            except SitemapNotAvailableError:
                # Re-raise sitemap not available
                raise
            except ET.ParseError as e:
                # XML parse error - sitemap exists but malformed
                if idx == 0:
                    raise SitemapNotAvailableError(f"Sitemap XML parse error: {e}")
                # Otherwise, we've reached the end
                break
            except Exception as e:
                # Network error or other issue
                if idx == 0:
                    raise SitemapNotAvailableError(f"Failed to fetch sitemap: {e}")
                logger.debug(f"Sitemap discovery ended at index {idx}: {e}")
                break

        # If we discovered 0 products, sitemap is either empty or doesn't exist properly
        if len(discovered) == 0:
            raise SitemapNotAvailableError("Sitemap returned 0 products")

        result = list(discovered)
        return result[:limit] if limit else result

    def _discover_via_categories(self, limit: Optional[int] = None) -> list[str]:
        logger.info(f"[{self.store_name}] Discovering via category tree...")

        # Use a reference region for discovery
        ref_region = self.config.get("discovery_region")
        if ref_region and ref_region in self.regions:
            cfg = self.regions[ref_region]
            cookie = self.resolver.get_segment_cookie(
                cfg["cep"], cfg["sc"], cfg.get("hub_id")
            )
            if cookie:
                self.session.cookies.set("vtex_segment", cookie)

        dept_ids = self._get_department_ids()
        discovered = set()
        api_url = f"{self.base_url}/api/catalog_system/pub/products/search"

        for dept_id in dept_ids:
            if limit and len(discovered) >= limit:
                break
            start = 0
            while True:
                if limit and len(discovered) >= limit:
                    break
                params = {
                    "fq": f"C:{dept_id}",
                    "_from": start,
                    "_to": start + 49,
                    "sc": self.regions[
                        self.config.get("discovery_region", list(self.regions.keys())[0])
                    ]["sc"],
                }
                try:
                    resp = self.session.get(api_url, params=params, timeout=15)
                    if resp.status_code not in [200, 206]:
                        break
                    items = resp.json()
                    if not items:
                        break
                    new_ids = {i["productId"] for i in items if "productId" in i}
                    discovered.update(new_ids)
                    start += 50
                    if len(items) < 50:
                        break
                except Exception as e:
                    logger.warning(f"Category discovery error for dept {dept_id} at offset {start}: {e}")
                    break
                time.sleep(self.request_delay)
            logger.info(f"  dept {dept_id}: total unique IDs = {len(discovered)}")

        result = list(discovered)
        return result[:limit] if limit else result

    def _get_department_ids(self) -> list[int]:
        try:
            url = f"{self.base_url}/api/catalog_system/pub/category/tree/3"
            resp = self.session.get(url, timeout=15)
            return [c["id"] for c in resp.json()]
        except Exception as e:
            logger.error(f"Failed to fetch category tree: {e}")
            return []

    # ── Scraping strategies ─────────────────────────────────────

    def _set_region_cookie(self, region_key: str) -> bool:
        cfg = self.regions[region_key]
        cookie = self.resolver.get_segment_cookie(
            cfg["cep"], cfg["sc"], cfg.get("hub_id")
        )
        if not cookie:
            logger.error(f"Failed to build cookie for {region_key}")
            return False
        if self.cookie_domain:
            self.session.cookies.set(
                "vtex_segment", cookie, domain=self.cookie_domain
            )
        else:
            self.session.cookies.set("vtex_segment", cookie)
        return True

    def _scrape_by_ids(self, region_key: str, product_ids: list[str]):
        """Global discovery mode: batch-fetch products by ID per region."""
        cfg = self.regions[region_key]
        logger.info(
            f"[{self.store_name}/{region_key}] Scraping {len(product_ids)} products "
            f"(CEP={cfg['cep']}, SC={cfg['sc']})"
        )

        if not self._set_region_cookie(region_key):
            return

        base_path = self.get_output_path(region_key)
        batches_dir = base_path / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)
        final_file = base_path / f"{self.store_name}_{region_key}_full.parquet"
        api_url = f"{self.base_url}/api/catalog_system/pub/products/search"

        # Use per-store database for parallel execution
        metrics = get_metrics_collector(
            db_path="data/metrics/{store}_runs.duckdb",
            store_name=self.store_name
        )

        for i in range(0, len(product_ids), self.batch_size):
            chunk = product_ids[i : i + self.batch_size]
            batch_file = batches_dir / f"batch_{i // self.batch_size:05d}.parquet"
            batch_number = i // self.batch_size
            fq = ",".join(f"productId:{pid}" for pid in chunk)
            params = {
                "fq": fq,
                "_from": 0,
                "_to": len(chunk) - 1,
                "sc": cfg["sc"],
            }

            with metrics.track_batch(batch_number, region=region_key) as batch:
                try:
                    resp = self.session.get(api_url, params=params, timeout=20)
                    batch.api_status_code = resp.status_code
                    if resp.status_code in [200, 206]:
                        items = resp.json()
                        # Phase 2: Validate products before saving
                        validated_items = self.validate_products(items)
                        batch.products_count = len(validated_items)
                        if validated_items:
                            self.save_batch(validated_items, batch_file, region_key)
                    else:
                        logger.warning(f"[{region_key}] API returned status {resp.status_code} for batch {batch_number}")
                        batch.success = False
                except Exception as e:
                    logger.error(f"Batch {batch_number} error at offset {i}: {e}")
                    batch.success = False

            if i % 500 == 0 and i > 0:
                logger.info(f"  progress: {i}/{len(product_ids)}")
            time.sleep(self.request_delay)

        self.consolidate_batches(batches_dir, final_file)
        self.validate_run(region_key, final_file)

    def _scrape_by_ids_parallel(self, region_key: str, product_ids: list[str]):
        """
        Thread-safe version of _scrape_by_ids for parallel execution.

        Each thread gets its own session to avoid race conditions.
        Uses global rate limiter to respect VTEX API limits.
        """
        import requests  # Import here for thread-local session

        cfg = self.regions[region_key]
        logger.info(
            f"[{self.store_name}/{region_key}] Scraping {len(product_ids)} products "
            f"(CEP={cfg['cep']}, SC={cfg['sc']}) [PARALLEL]"
        )

        # Create thread-local session
        session = requests.Session()
        session.headers.update(self.session.headers)  # Copy headers from main session

        # Set region cookie
        resolver = RegionResolver(session, self.base_url)
        cookie = resolver.get_segment_cookie(cfg["cep"], cfg["sc"], cfg.get("hub_id"))
        if not cookie:
            logger.error(f"Failed to build cookie for {region_key}")
            return

        if self.cookie_domain:
            session.cookies.set("vtex_segment", cookie, domain=self.cookie_domain)
        else:
            session.cookies.set("vtex_segment", cookie)

        base_path = self.get_output_path(region_key)
        batches_dir = base_path / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)
        final_file = base_path / f"{self.store_name}_{region_key}_full.parquet"
        api_url = f"{self.base_url}/api/catalog_system/pub/products/search"

        # Use per-store database for parallel execution
        metrics = get_metrics_collector(
            db_path="data/metrics/{store}_runs.duckdb",
            store_name=self.store_name
        )

        for i in range(0, len(product_ids), self.batch_size):
            chunk = product_ids[i : i + self.batch_size]
            batch_file = batches_dir / f"batch_{i // self.batch_size:05d}.parquet"
            batch_number = i // self.batch_size
            fq = ",".join(f"productId:{pid}" for pid in chunk)
            params = {
                "fq": fq,
                "_from": 0,
                "_to": len(chunk) - 1,
                "sc": cfg["sc"],
            }

            with metrics.track_batch(batch_number, region=region_key) as batch:
                # Use rate limiter to respect VTEX API limits
                with self.rate_limiter.limit():
                    try:
                        resp = session.get(api_url, params=params, timeout=20)
                        batch.api_status_code = resp.status_code
                        if resp.status_code in [200, 206]:
                            items = resp.json()
                            # Phase 2: Validate products before saving
                            validated_items = self.validate_products(items)
                            batch.products_count = len(validated_items)
                            if validated_items:
                                self.save_batch(validated_items, batch_file, region_key)
                            elif len(items) > 0:
                                # Log warning only if API returned products but all failed validation
                                logger.warning(f"[{region_key}] All {len(items)} products in batch {batch_number} failed validation")
                        else:
                            logger.warning(f"[{region_key}] API returned status {resp.status_code} for batch {batch_number}")
                            batch.success = False
                    except Exception as e:
                        logger.error(f"Batch {batch_number} error at offset {i}: {e}")
                        batch.success = False

            if i % 500 == 0 and i > 0:
                logger.info(f"  [{region_key}] progress: {i}/{len(product_ids)}")

        # Close thread-local session
        session.close()

        self.consolidate_batches(batches_dir, final_file)
        self.validate_run(region_key, final_file)

    def _scrape_by_departments(self, region_key: str, limit: Optional[int] = None):
        """Per-region mode: iterate departments and fetch all products (Giassi-style)."""
        cfg = self.regions[region_key]
        logger.info(
            f"[{self.store_name}/{region_key}] Scraping by department "
            f"(CEP={cfg['cep']}, SC={cfg['sc']})"
        )

        if not self._set_region_cookie(region_key):
            return

        base_path = self.get_output_path(region_key)
        batches_dir = base_path / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)
        final_file = base_path / f"{self.store_name}_{region_key}_full.parquet"

        dept_ids = self._get_department_ids()
        total_collected = 0
        batch_counter = 0
        api_url = f"{self.base_url}/api/catalog_system/pub/products/search"
        metrics = get_metrics_collector()

        for dept_id in dept_ids:
            if limit and total_collected >= limit:
                break

            start = 0
            while True:
                if limit and total_collected >= limit:
                    break
                if start > 2500:
                    break

                params = {
                    "fq": f"C:{dept_id}",
                    "_from": start,
                    "_to": start + 49,
                    "sc": cfg["sc"],
                    "O": "OrderByScoreDESC",
                }

                with metrics.track_batch(batch_counter, region=region_key) as batch:
                    try:
                        resp = self.session.get(api_url, params=params, timeout=20)
                        batch.api_status_code = resp.status_code
                        if resp.status_code not in [200, 206]:
                            batch.success = False
                            break
                        items = resp.json()
                        if not items:
                            break

                        # Phase 2: Validate products before saving
                        validated_items = self.validate_products(items)
                        batch.products_count = len(validated_items)
                        if not validated_items:
                            break

                        batch_file = (
                            batches_dir / f"dept_{dept_id}_batch_{start:05d}.parquet"
                        )
                        self.save_batch(
                            validated_items,
                            batch_file,
                            region_key,
                            extra_metadata={"dept_id": dept_id},
                        )
                        total_collected += len(validated_items)
                        start += 50
                        batch_counter += 1
                        if len(validated_items) < 50:
                            break
                    except Exception as e:
                        logger.error(f"Error dept {dept_id} offset {start}: {e}")
                        batch.success = False
                        break

                time.sleep(self.request_delay)

            logger.info(f"  dept {dept_id}: total collected = {total_collected}")

        self.consolidate_batches(batches_dir, final_file)
        self.validate_run(region_key, final_file)
