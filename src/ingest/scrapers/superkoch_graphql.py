"""
Super Koch GraphQL Scraper.

Super Koch uses the Osuper platform with a GraphQL API.
Discovery: Sitemap for product IDs
Scraping: GraphQL queries for product details by store_id
"""

import json
import time
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger
from pydantic import ValidationError

from .base import BaseScraper
from src.schemas.superkoch import SuperKochProduct
from src.observability.metrics import get_metrics_collector


class SuperKochGraphQLScraper(BaseScraper):
    """
    GraphQL-based scraper for Super Koch (Osuper platform).

    Discovery: Sitemap XML to extract product IDs
    Scraping: GraphQL API for product details per store
    """

    def __init__(self, store_name: str, config: dict):
        super().__init__(store_name, config)
        self.api_url = config.get("api_url", "https://api.superkoch.com.br:443/graphql")
        self.sitemap_pattern = config.get("sitemap_pattern", "/sitemap.xml")
        self.validation_errors_count = 0

    def discover_products(self, limit: Optional[int] = None) -> List[str]:
        """
        Discover product IDs from sitemap.

        Returns:
            List of product IDs (e.g., ["7804972", "7804973", ...])
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
                # Extract product ID from URL pattern: /produtos/{ID}/{slug}
                if "/produtos/" in product_url:
                    match = re.search(r'/produtos/(\d+)/', product_url)
                    if match:
                        product_id = match.group(1)
                        discovered.append(product_id)
                        if limit and len(discovered) >= limit:
                            break

            logger.info(f"[{self.store_name}] Discovered {len(discovered)} product IDs")
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
            List of sampled product IDs
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
            List of new product IDs not in previous run
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

        # Read previous product IDs
        import pandas as pd
        df = pd.read_parquet(latest_file, columns=["productId"])
        previous_products = set(df["productId"].astype(str))

        # Find new products
        new_products = list(current_products - previous_products)
        logger.info(
            f"[{self.store_name}] Found {len(new_products)} new products "
            f"(out of {len(current_products)} total)"
        )

        return new_products[:limit] if limit else new_products

    def scrape_region(self, region_key: str, product_ids: List[str]):
        """
        Scrape products for a specific region using GraphQL API.

        Args:
            region_key: Region identifier from config
            product_ids: List of product IDs to scrape
        """
        if region_key not in self.regions:
            logger.error(f"Region '{region_key}' not found in config")
            return

        region_cfg = self.regions[region_key]
        store_id = region_cfg.get("store_id")

        if not store_id:
            logger.error(f"store_id not configured for region '{region_key}'")
            return

        logger.info(
            f"[{self.store_name}/{region_key}] Starting scrape "
            f"({len(product_ids)} products, store_id={store_id})"
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
        total = len(product_ids)
        batch_num = 0
        all_products = []

        for i in range(0, total, self.batch_size):
            batch = product_ids[i:i + self.batch_size]
            batch_num += 1

            logger.info(
                f"  [{batch_num}] Processing {len(batch)} products "
                f"({i+1}-{min(i+len(batch), total)} of {total})"
            )

            with metrics.track_batch(batch_num) as batch_metrics:
                batch_products = []

                for product_id in batch:
                    try:
                        product_data = self._fetch_product_graphql(product_id, store_id)
                        if product_data:
                            # Validate with Pydantic schema
                            try:
                                validated = SuperKochProduct(**product_data)
                                batch_products.append(validated.model_dump())
                            except ValidationError as ve:
                                logger.warning(
                                    f"Validation failed for product {product_id}: {ve}"
                                )
                                self.validation_errors_count += 1
                                continue
                        time.sleep(self.request_delay)
                    except Exception as e:
                        logger.warning(f"Failed to fetch product {product_id}: {e}")
                        continue

                batch_metrics.products_count = len(batch_products)
                all_products.extend(batch_products)

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
            f"{count} products saved"
        )

    def _fetch_product_graphql(self, product_id: str, store_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch product details via GraphQL API.

        Args:
            product_id: Product ID
            store_id: Store ID for pricing/inventory

        Returns:
            Product data dict or None if failed
        """
        query = """
        query GetProduct($productId: ID!, $storeId: ID!) {
          product(id: $productId, storeId: $storeId) {
            id
            name
            slug
            brand
            gtin
            image {
              url
            }
            pricing(storeId: $storeId) {
              price
              listPrice
            }
            quantity(storeId: $storeId) {
              quantity
              minQuantity
              maxQuantity
            }
            saleUnit
            categories {
              id
              name
              slug
            }
          }
        }
        """

        variables = {
            "productId": product_id,
            "storeId": store_id
        }

        payload = {
            "query": query,
            "variables": variables
        }

        try:
            resp = self.session.post(
                self.api_url,
                json=payload,
                timeout=15,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )

            if resp.status_code != 200:
                logger.warning(
                    f"GraphQL request failed for product {product_id}: "
                    f"status {resp.status_code}"
                )
                return None

            data = resp.json()

            # Check for GraphQL errors
            if "errors" in data:
                logger.warning(
                    f"GraphQL errors for product {product_id}: {data['errors']}"
                )
                return None

            # Extract product data
            product = data.get("data", {}).get("product")
            if not product:
                logger.debug(f"No product data returned for {product_id}")
                return None

            # Normalize to flat structure
            normalized = self._normalize_product(product, store_id)
            return normalized

        except Exception as e:
            logger.warning(f"Exception fetching product {product_id}: {e}")
            return None

    def _normalize_product(self, product: Dict[str, Any], store_id: str) -> Dict[str, Any]:
        """
        Normalize GraphQL product response to flat structure.

        Args:
            product: Raw GraphQL product data
            store_id: Store ID

        Returns:
            Normalized product dict compatible with schemas
        """
        pricing = product.get("pricing") or {}
        quantity = product.get("quantity") or {}
        image = product.get("image") or {}
        categories = product.get("categories") or []

        return {
            "productId": str(product.get("id", "")),
            "productName": product.get("name", ""),
            "brand": product.get("brand", ""),
            "ean": product.get("gtin", ""),
            "price": pricing.get("price", 0.0),
            "listPrice": pricing.get("listPrice", 0.0),
            "available": quantity.get("quantity", 0) > 0,
            "stock": quantity.get("quantity", 0),
            "imageUrl": image.get("url", ""),
            "productUrl": f"{self.base_url}/produtos/{product.get('id')}/{product.get('slug', '')}",
            "categories": [cat.get("name", "") for cat in categories],
            "categoryIds": [str(cat.get("id", "")) for cat in categories],
            "saleUnit": product.get("saleUnit", "UN"),
            "storeId": store_id,
            # Metadata
            "platform": "osuper",
            "scrapedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }