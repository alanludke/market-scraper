"""
Super Koch GraphQL Scraper.

Super Koch uses the Osuper e-commerce platform with GraphQL API.
Uses sitemap for product discovery, then fetches details via GraphQL queries.

API: https://api.superkoch.com.br:443/graphql
Platform: Osuper (custom)
Region system: store_id (not CEP-based like VTEX)
"""

import json
import re
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger
from pydantic import ValidationError

from .base import BaseScraper
from src.observability.metrics import get_metrics_collector


class SuperKochScraper(BaseScraper):
    """
    GraphQL-based scraper for Super Koch (Osuper platform).

    Discovery: Sitemap (single XML file with all products)
    Scraping: GraphQL API with store-specific pricing
    """

    def __init__(self, store_name: str, config: dict):
        super().__init__(store_name, config)
        self.api_url = config.get("api_url", "https://api.superkoch.com.br:443/graphql")
        self.sitemap_pattern = config.get("sitemap_pattern", "/sitemap.xml")
        self.validation_errors_count = 0

    def discover_products(self, limit: Optional[int] = None) -> List[str]:
        """
        Discover product IDs from sitemap.

        Super Koch has a single sitemap.xml with ~700 products.
        Product URL pattern: /produtos/{ID}/{slug}

        Returns:
            List of product IDs (strings)
        """
        logger.info(f"[{self.store_name}] Discovering products from sitemap...")
        discovered = set()

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
                # Extract ID from URL pattern: /produtos/{ID}/{slug}
                match = re.search(r'/produtos/(\d+)/', product_url)
                if match:
                    product_id = match.group(1)
                    discovered.add(product_id)

            logger.info(f"[{self.store_name}] Discovered {len(discovered)} product IDs from sitemap")

        except ET.ParseError as e:
            raise Exception(f"Sitemap XML parse error: {e}")
        except Exception as e:
            raise Exception(f"Failed to fetch sitemap: {e}")

        result = list(discovered)
        return result[:limit] if limit else result

    def scrape_region(self, region_key: str, product_ids: List[str]):
        """
        Scrape products for a specific region (store).

        Args:
            region_key: Region identifier (e.g., "balneario_camboriu")
            product_ids: List of product IDs to scrape
        """
        cfg = self.regions[region_key]
        store_id = cfg.get("store_id")
        if not store_id:
            logger.error(f"[{self.store_name}/{region_key}] No store_id configured")
            return

        logger.info(
            f"[{self.store_name}/{region_key}] Scraping {len(product_ids)} products "
            f"(store_id={store_id}, {cfg.get('name', region_key)})"
        )

        base_path = self.get_output_path(region_key)
        batches_dir = base_path / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)
        final_file = base_path / f"{self.store_name}_{region_key}_full.parquet"

        # Use per-store database for parallel execution
        metrics = get_metrics_collector(
            db_path="data/metrics/{store}_runs.duckdb",
            store_name=self.store_name
        )

        # Process products in batches
        for i in range(0, len(product_ids), self.batch_size):
            chunk = product_ids[i : i + self.batch_size]
            batch_file = batches_dir / f"batch_{i // self.batch_size:05d}.parquet"
            batch_number = i // self.batch_size

            with metrics.track_batch(batch_number, region=region_key) as batch:
                try:
                    # Fetch products via GraphQL
                    products = self._fetch_products_graphql(chunk, store_id)
                    batch.products_count = len(products)

                    if products:
                        self.save_batch(products, batch_file, region_key)
                    else:
                        logger.warning(
                            f"[{region_key}] Batch {batch_number} returned 0 products"
                        )

                except Exception as e:
                    logger.error(f"Batch {batch_number} error at offset {i}: {e}")
                    batch.success = False

            if i % 100 == 0 and i > 0:
                logger.info(f"  progress: {i}/{len(product_ids)}")

            time.sleep(self.request_delay)

        # Consolidate batches
        self.consolidate_batches(batches_dir, final_file)
        self.validate_run(region_key, final_file, min_expected=100)

    def _fetch_products_graphql(
        self,
        product_ids: List[str],
        store_id: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch product details via GraphQL API.

        Args:
            product_ids: List of product IDs to fetch
            store_id: Store ID for pricing/availability

        Returns:
            List of product dictionaries
        """
        products = []

        for product_id in product_ids:
            try:
                product = self._fetch_single_product(product_id, store_id)
                if product:
                    products.append(product)
            except Exception as e:
                logger.warning(f"Failed to fetch product {product_id}: {e}")
                continue

        return products

    def _fetch_single_product(
        self,
        product_id: str,
        store_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch single product via GraphQL.

        GraphQL Query:
        {
          product(id: "ID", storeId: "STORE_ID") {
            id
            name
            brand
            ean
            pricing(storeId: "STORE_ID") {
              price
              originalPrice
            }
            quantity(storeId: "STORE_ID") {
              available
              stock
            }
            image {
              url
            }
            saleUnit
          }
        }
        """
        query = """
        query GetProduct($productId: ID!, $storeId: ID!) {
          product(id: $productId, storeId: $storeId) {
            id
            iid
            name
            slug
            brand
            ean
            description
            saleUnit
            image {
              url
              thumborUrl
            }
            pricing(storeId: $storeId) {
              price
              originalPrice
              discountPercentage
            }
            quantity(storeId: $storeId) {
              available
              stock
              minQuantity
              maxQuantity
            }
            productType
            sellByWeightAndUnit
            supportsExpressDelivery
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
                    f"GraphQL API returned status {resp.status_code} for product {product_id}"
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
            if "data" in data and "product" in data["data"]:
                product = data["data"]["product"]
                if product:
                    # Flatten nested structures for easier processing
                    return self._normalize_product(product, store_id)

            return None

        except Exception as e:
            logger.error(f"Exception fetching product {product_id}: {e}")
            return None

    def _normalize_product(
        self,
        raw_product: Dict[str, Any],
        store_id: str
    ) -> Dict[str, Any]:
        """
        Normalize GraphQL product structure to flat schema.

        Args:
            raw_product: Raw GraphQL response
            store_id: Store ID for metadata

        Returns:
            Normalized product dictionary
        """
        # Extract pricing
        pricing = raw_product.get("pricing") or {}
        price = pricing.get("price")
        original_price = pricing.get("originalPrice")
        discount_pct = pricing.get("discountPercentage")

        # Extract quantity/stock
        quantity = raw_product.get("quantity") or {}
        stock = quantity.get("stock", 0)
        available = quantity.get("available", False)
        min_qty = quantity.get("minQuantity", 1)
        max_qty = quantity.get("maxQuantity", 999)

        # Extract image
        image = raw_product.get("image") or {}
        image_url = image.get("url") or image.get("thumborUrl")

        # Build normalized product
        normalized = {
            "productId": raw_product.get("id"),
            "productName": raw_product.get("name"),
            "brand": raw_product.get("brand"),
            "ean": raw_product.get("ean"),
            "description": raw_product.get("description"),
            "saleUnit": raw_product.get("saleUnit"),
            "productType": raw_product.get("productType"),
            # Pricing
            "price": price,
            "listPrice": original_price,
            "discountPercentage": discount_pct,
            "sellingPrice": price,  # For compatibility
            # Stock
            "available": available,
            "stock": stock,
            "minQuantity": min_qty,
            "maxQuantity": max_qty,
            # Images
            "imageUrl": image_url,
            # Metadata
            "store_id": store_id,
            "slug": raw_product.get("slug"),
            "sellByWeightAndUnit": raw_product.get("sellByWeightAndUnit"),
            "supportsExpressDelivery": raw_product.get("supportsExpressDelivery"),
            "iid": raw_product.get("iid"),  # Internal ID / SKU
        }

        return normalized
