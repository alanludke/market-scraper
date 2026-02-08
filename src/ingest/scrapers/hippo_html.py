"""
Hippo Supermercados HTML Scraper.

Hippo uses the Osuper platform with GraphQL API that requires authentication.
Instead, we scrape product pages directly and extract JSON-LD structured data.

Discovery: Sitemap for product URLs
Scraping: HTML pages with JSON-LD extraction
"""

import json
import time
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger
from bs4 import BeautifulSoup
from pydantic import ValidationError

from .base import BaseScraper
from src.schemas.hippo import HippoProduct
from src.observability.metrics import get_metrics_collector


class HippoHTMLScraper(BaseScraper):
    """
    HTML-based scraper for Hippo Supermercados (Osuper platform).

    Discovery: Sitemap XML to extract product URLs
    Scraping: HTML pages with JSON-LD structured data extraction
    """

    def __init__(self, store_name: str, config: dict):
        super().__init__(store_name, config)
        self.sitemap_pattern = config.get("sitemap_pattern", "/sitemap.xml")
        self.validation_errors_count = 0

    def discover_products(self, limit: Optional[int] = None) -> List[str]:
        """
        Discover product URLs from sitemap.

        Returns:
            List of product URLs (e.g., ["https://www.hipposupermercados.com.br/produtos/3840/...", ...])
        """
        logger.info(f"[{self.store_name}] Discovering products from sitemap...")
        discovered = []

        url = f"{self.base_url}{self.sitemap_pattern}"
        try:
            resp = self.session.get(url, timeout=20)

            if resp.status_code != 200:
                raise Exception(f"Sitemap not found: {url} (status {resp.status_code})")

            # Parse sitemap XML
            root = ET.fromstring(resp.content)
            ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            for loc in root.findall(".//s:loc", ns):
                product_url = loc.text
                # Filter only product URLs
                if "/produtos/" in product_url:
                    discovered.append(product_url)
                    if limit and len(discovered) >= limit:
                        break

            logger.info(f"[{self.store_name}] Discovered {len(discovered)} product URLs")
            return discovered[:limit] if limit else discovered

        except ET.ParseError as e:
            raise Exception(f"Sitemap XML parse error: {e}")
        except Exception as e:
            raise Exception(f"Failed to fetch sitemap: {e}")

    def discover_sample(
        self,
        sample_rate: float = 0.1,
        limit: Optional[int] = None
    ) -> List[str]:
        """
        Discover a random sample of products for incremental scraping.

        Args:
            sample_rate: Percentage of products to sample (0.1 = 10%)
            limit: Max products to return (optional)

        Returns:
            List of sampled product URLs
        """
        import random

        all_products = self.discover_products(limit=None)
        sample_size = int(len(all_products) * sample_rate)

        if limit:
            sample_size = min(sample_size, limit)

        sampled = random.sample(all_products, sample_size)
        logger.info(
            f"[{self.store_name}] Sampled {len(sampled)} products "
            f"({sample_rate*100:.0f}% of {len(all_products)})"
        )
        return sampled

    def discover_new_products(self, limit: Optional[int] = None) -> List[str]:
        """
        Discover new products by comparing with previous run.

        Args:
            limit: Max products to return (optional)

        Returns:
            List of new product URLs not in previous run
        """
        # Get current products
        current_products = set(self.discover_products(limit=None))

        # Find latest run file
        bronze_dir = Path("data/bronze") / f"supermarket={self.store_name}"
        if not bronze_dir.exists():
            logger.warning("No previous run found, returning all products")
            result = list(current_products)
            return result[:limit] if limit else result

        # Find most recent parquet file
        parquet_files = list(bronze_dir.rglob("*.parquet"))
        if not parquet_files:
            logger.warning("No previous run found, returning all products")
            result = list(current_products)
            return result[:limit] if limit else result

        latest_file = max(parquet_files, key=lambda p: p.stat().st_mtime)

        # Read previous product URLs
        import pandas as pd
        df = pd.read_parquet(latest_file, columns=["productUrl"])
        previous_products = set(df["productUrl"])

        # Find new products
        new_products = list(current_products - previous_products)
        logger.info(
            f"[{self.store_name}] Found {len(new_products)} new products "
            f"(out of {len(current_products)} total)"
        )

        return new_products[:limit] if limit else new_products

    def scrape_region(self, region_key: str, product_urls: List[str]):
        """
        Scrape products for a specific region.

        Note: Hippo doesn't have traditional region-based pricing like VTEX stores.
        The region_key is kept for consistency with BaseScraper interface.

        Args:
            region_key: Region identifier from config
            product_urls: List of product URLs to scrape
        """
        if region_key not in self.regions:
            logger.error(f"Region '{region_key}' not found in config")
            return

        region_cfg = self.regions[region_key]

        logger.info(
            f"[{self.store_name}/{region_key}] Starting scrape "
            f"({len(product_urls)} products)"
        )

        # Setup metrics tracking
        metrics = get_metrics_collector(
            db_path=f"data/metrics/{self.store_name}_runs.duckdb",
            store_name=self.store_name
        )

        output_dir = self.get_output_path(region_key)
        batches_dir = output_dir / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)

        # Process in batches
        total = len(product_urls)
        batch_num = 0

        for i in range(0, total, self.batch_size):
            batch = product_urls[i:i + self.batch_size]
            batch_num += 1

            logger.info(
                f"  [{batch_num}] Processing {len(batch)} products "
                f"({i+1}-{min(i+len(batch), total)} of {total})"
            )

            with metrics.track_batch(batch_num) as batch_metrics:
                batch_products = []

                for product_url in batch:
                    try:
                        product_data = self._fetch_product_html(product_url, region_cfg)
                        if product_data:
                            # Validate with Pydantic schema
                            try:
                                validated = HippoProduct(**product_data)
                                batch_products.append(validated.model_dump())
                            except ValidationError as ve:
                                logger.warning(
                                    f"Validation failed for {product_url}: {ve}"
                                )
                                self.validation_errors_count += 1
                                continue

                        time.sleep(self.request_delay)

                    except Exception as e:
                        logger.warning(f"Failed to fetch {product_url}: {e}")
                        continue

                batch_metrics.products_count = len(batch_products)

                # Save batch
                if batch_products:
                    batch_file = batches_dir / f"batch_{batch_num:04d}.parquet"
                    self.save_batch(
                        batch_products,
                        batch_file,
                        region_key,
                        extra_metadata={"batch_number": batch_num}
                    )

        # Consolidate batches
        final_file = output_dir / f"run_{self.run_id}.parquet"
        count = self.consolidate_batches(batches_dir, final_file)

        # Validate
        self.validate_run(region_key, final_file, min_expected=100)

        logger.info(
            f"[{self.store_name}/{region_key}] Scrape completed: "
            f"{count} products saved (validation errors: {self.validation_errors_count})"
        )

    def _fetch_product_html(
        self,
        product_url: str,
        region_cfg: dict
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch product details from HTML page.

        Args:
            product_url: Product page URL
            region_cfg: Region configuration

        Returns:
            Product data dict or None if failed
        """
        try:
            resp = self.session.get(product_url, timeout=15)

            if resp.status_code != 200:
                logger.warning(
                    f"Failed to fetch {product_url}: status {resp.status_code}"
                )
                return None

            soup = BeautifulSoup(resp.content, 'html.parser')

            # Extract JSON-LD structured data
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            if not json_ld_scripts:
                logger.debug(f"No JSON-LD found in {product_url}")
                return None

            # Find the Product schema
            product_data = None
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if data.get("@type") == "Product":
                        product_data = data
                        break
                except:
                    continue

            if not product_data:
                logger.debug(f"No Product JSON-LD found in {product_url}")
                return None

            # Normalize to flat structure
            normalized = self._normalize_product(product_data, product_url, region_cfg)
            return normalized

        except Exception as e:
            logger.warning(f"Exception fetching {product_url}: {e}")
            return None

    def _normalize_product(
        self,
        json_ld: Dict[str, Any],
        product_url: str,
        region_cfg: dict
    ) -> Dict[str, Any]:
        """
        Normalize JSON-LD product data to flat structure.

        Args:
            json_ld: JSON-LD Product schema data
            product_url: Product page URL
            region_cfg: Region configuration

        Returns:
            Normalized product dict compatible with HippoProduct schema
        """
        # Extract offer data
        offers = json_ld.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        # Extract price
        price = float(offers.get("price", 0))

        # Extract availability
        availability_url = offers.get("availability", "")
        available = "InStock" in availability_url

        # Extract brand
        brand_obj = json_ld.get("brand", {})
        brand = brand_obj.get("name", "") if isinstance(brand_obj, dict) else str(brand_obj)

        # Extract image
        images = json_ld.get("image", [])
        image_url = images[0] if isinstance(images, list) and images else (images if isinstance(images, str) else "")

        # Extract product ID from SKU or URL
        product_id = json_ld.get("sku", "")
        if not product_id:
            # Extract from URL: /produtos/{ID}/...
            match = re.search(r'/produtos/(\d+)/', product_url)
            product_id = match.group(1) if match else ""

        return {
            "productId": str(product_id),
            "productName": json_ld.get("name", ""),
            "brand": brand,
            "ean": json_ld.get("gtin13") or json_ld.get("gtin") or None,
            "price": price,
            "listPrice": price,  # JSON-LD doesn't have separate listPrice
            "available": available,
            "stock": 999 if available else 0,  # JSON-LD doesn't have quantity
            "imageUrl": image_url,
            "productUrl": product_url,
            "categories": [],  # Not available in JSON-LD
            "categoryIds": [],  # Not available in JSON-LD
            "saleUnit": "UN",  # Default, not in JSON-LD
            "storeId": region_cfg.get("store_id", ""),
            # Metadata
            "platform": "osuper",
            "scrapedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
