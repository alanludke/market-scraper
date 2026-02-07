"""
Angeloni HTML Scraper.

Angeloni uses VTEX platform but blocks API access, so we scrape product pages directly.
Uses sitemap for discovery, then fetches HTML pages and parses product data.
"""

import json
import time
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger
from bs4 import BeautifulSoup
import pandas as pd
from pydantic import ValidationError

from .base import BaseScraper
from src.schemas.vtex import VTEXProduct
from src.observability.metrics import get_metrics_collector


class AngeloniHTMLScraper(BaseScraper):
    """
    HTML-based scraper for Angeloni (VTEX platform with blocked API).

    Discovery: Sitemaps
    Scraping: Direct HTML parsing
    """

    def __init__(self, store_name: str, config: dict):
        super().__init__(store_name, config)
        self.sitemap_pattern = config.get("sitemap_pattern", "/super/sitemap/product-{n}.xml")
        self.sitemap_start_index = config.get("sitemap_start_index", 0)
        self.validation_errors_count = 0

    def discover_products(self, limit: Optional[int] = None) -> List[str]:
        """
        Discover product URLs from sitemaps.

        Returns:
            List of product URLs (not IDs, since we scrape HTML)
        """
        logger.info(f"[{self.store_name}] Discovering products from sitemap...")
        discovered = []
        idx = self.sitemap_start_index

        while True:
            if limit and len(discovered) >= limit:
                discovered = discovered[:limit]
                break

            url = f"{self.base_url}{self.sitemap_pattern.replace('{n}', str(idx))}"
            try:
                resp = self.session.get(url, timeout=20)

                if resp.status_code != 200:
                    if idx == self.sitemap_start_index:
                        raise Exception(f"First sitemap not found: {url}")
                    # Reached end of sitemaps
                    break

                # Parse sitemap XML
                root = ET.fromstring(resp.content)
                ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                count_before = len(discovered)

                for loc in root.findall(".//s:loc", ns):
                    product_url = loc.text
                    if "/p" in product_url:  # Filter only product URLs
                        # Fix: Angeloni sitemap URLs are missing /super/ prefix
                        if "/super/" not in product_url:
                            product_url = product_url.replace("://www.angeloni.com.br/", "://www.angeloni.com.br/super/")
                        discovered.append(product_url)
                        if limit and len(discovered) >= limit:
                            break

                logger.info(
                    f"  sitemap-{idx}: +{len(discovered) - count_before} "
                    f"(total: {len(discovered)})"
                )
                idx += 1

            except ET.ParseError as e:
                if idx == self.sitemap_start_index:
                    raise Exception(f"Sitemap XML parse error: {e}")
                break
            except Exception as e:
                if idx == self.sitemap_start_index:
                    raise Exception(f"Failed to fetch sitemap: {e}")
                logger.debug(f"Sitemap discovery ended at index {idx}: {e}")
                break

        logger.info(f"[{self.store_name}] Discovered {len(discovered)} product URLs")
        return discovered

    def discover_products_incremental(
        self,
        days_back: int = 7,
        limit: Optional[int] = None
    ) -> List[str]:
        """
        Discover only recently modified products using sitemap lastmod.

        Args:
            days_back: Only include products modified in last N days (default: 7)
            limit: Max products to return (optional)

        Returns:
            List of product URLs modified in the specified timeframe
        """
        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(days=days_back)
        logger.info(
            f"[{self.store_name}] Discovering products modified since "
            f"{cutoff_date.strftime('%Y-%m-%d')} ({days_back} days back)"
        )

        discovered = []
        idx = self.sitemap_start_index
        total_checked = 0
        skipped_old = 0

        while True:
            if limit and len(discovered) >= limit:
                discovered = discovered[:limit]
                break

            url = f"{self.base_url}{self.sitemap_pattern.replace('{n}', str(idx))}"
            try:
                resp = self.session.get(url, timeout=20)

                if resp.status_code != 200:
                    if idx == self.sitemap_start_index:
                        raise Exception(f"First sitemap not found: {url}")
                    break

                # Parse sitemap XML
                root = ET.fromstring(resp.content)
                ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                count_before = len(discovered)

                # Iterate over <url> elements (not just <loc>)
                for url_elem in root.findall(".//s:url", ns):
                    loc = url_elem.find("s:loc", ns)
                    lastmod = url_elem.find("s:lastmod", ns)

                    if loc is not None and "/p" in loc.text:
                        total_checked += 1
                        product_url = loc.text

                        # Fix: Angeloni sitemap URLs are missing /super/ prefix
                        if "/super/" not in product_url:
                            product_url = product_url.replace("://www.angeloni.com.br/", "://www.angeloni.com.br/super/")

                        # Check lastmod date
                        include_product = False

                        if lastmod is not None and lastmod.text:
                            try:
                                # Parse lastmod (format: 2026-02-05 or 2026-02-05T10:30:00)
                                mod_date_str = lastmod.text.split('T')[0]
                                mod_date = datetime.strptime(mod_date_str, '%Y-%m-%d')

                                if mod_date >= cutoff_date:
                                    include_product = True
                                else:
                                    skipped_old += 1
                            except ValueError as e:
                                logger.debug(f"Invalid lastmod format: {lastmod.text}")
                                include_product = True
                        else:
                            # No lastmod tag, include it (safer to not skip)
                            include_product = True

                        if include_product:
                            discovered.append(product_url)

                            if limit and len(discovered) >= limit:
                                break

                new_count = len(discovered) - count_before
                logger.info(
                    f"  sitemap-{idx}: +{new_count} recent "
                    f"(total: {len(discovered)}, skipped: {skipped_old})"
                )
                idx += 1

            except ET.ParseError as e:
                if idx == self.sitemap_start_index:
                    raise Exception(f"Sitemap XML parse error: {e}")
                break
            except Exception as e:
                if idx == self.sitemap_start_index:
                    raise Exception(f"Failed to fetch sitemap: {e}")
                logger.debug(f"Sitemap discovery ended at index {idx}: {e}")
                break

        logger.info(
            f"[{self.store_name}] Incremental discovery complete: "
            f"{len(discovered)} recent products (checked {total_checked}, "
            f"skipped {skipped_old} old)"
        )

        return discovered

    def scrape_product_page(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape a single product page and extract product data from HTML.

        Tries multiple extraction strategies:
        1. Microdata (schema.org Product)
        2. HTML parsing (class-based selectors)
        3. JavaScript __RUNTIME__ object

        Returns:
            Product dict compatible with VTEXProduct schema, or None if failed
        """
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"Failed to fetch {url}: HTTP {resp.status_code}")
                return None

            # Parse HTML
            soup = BeautifulSoup(resp.content, 'html.parser')

            # Strategy 1: Try microdata (itemtype="http://schema.org/Product")
            product_elem = soup.find(attrs={'itemtype': re.compile('Product', re.I)})
            if product_elem:
                return self._extract_from_microdata(product_elem, url)

            # Strategy 2: HTML class-based parsing
            product = self._extract_from_html(soup, url)
            if product:
                return product

            # Strategy 3: JavaScript __RUNTIME__ or similar
            product = self._extract_from_javascript(resp.text, url)
            if product:
                return product

            logger.warning(f"No product data extracted from {url}")
            return None

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None

    def _extract_from_microdata(self, elem: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """Extract product data from schema.org microdata."""
        try:
            def get_itemprop(name):
                tag = elem.find(attrs={'itemprop': name})
                return tag.get('content', '') if tag and tag.has_attr('content') else tag.get_text(strip=True) if tag else ''

            # Parse product ID from URL
            product_id = url.rstrip('/p').split('-')[-1]
            if not product_id.isdigit():
                product_id = '0'

            product = {
                'productId': product_id,
                'productName': get_itemprop('name'),
                'brand': get_itemprop('brand'),
                'linkText': url.split('/')[-2] if '/' in url else '',
                'productReference': '',
                'categoryId': None,
                'categories': [get_itemprop('category')] if get_itemprop('category') else [],
                'link': url,
                'description': get_itemprop('description'),
                'items': [{
                    'itemId': product_id,
                    'name': get_itemprop('name'),
                    'ean': get_itemprop('gtin') or get_itemprop('gtin13') or get_itemprop('gtin14'),
                    'variations': [],
                    'sellers': [{
                        'sellerId': '1',
                        'sellerName': 'Angeloni',
                        'addToCartLink': '',
                        'sellerDefault': True,
                        'commertialOffer': {
                            'Price': float(get_itemprop('price') or 0),
                            'ListPrice': float(get_itemprop('price') or 0),
                            'PriceWithoutDiscount': float(get_itemprop('price') or 0),
                            'AvailableQuantity': 100,  # Default assumption
                            'IsAvailable': get_itemprop('availability') != 'OutOfStock',
                        }
                    }],
                    'images': [
                        {
                            'imageId': '1',
                            'imageUrl': get_itemprop('image'),
                            'imageLabel': '',
                            'imageText': get_itemprop('name')
                        }
                    ] if get_itemprop('image') else [],
                }],
            }

            return product

        except Exception as e:
            logger.error(f"Microdata extraction failed: {e}")
            return None

    def _extract_from_html(self, soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """Extract product data from HTML class-based selectors (VTEX patterns)."""
        try:
            # Product name (common VTEX classes)
            name_elem = (
                soup.find('h1', class_=re.compile('productName|product-name', re.I)) or
                soup.find('h1')
            )
            product_name = name_elem.get_text(strip=True) if name_elem else ''

            # Price (common VTEX classes)
            price_elem = (
                soup.find(class_=re.compile('sellingPrice|best-price|price-best', re.I)) or
                soup.find('span', class_=re.compile('price', re.I))
            )
            price_text = price_elem.get_text(strip=True) if price_elem else '0'
            # Extract numeric value from "R$ 12,99"
            price = float(re.sub(r'[^\d,]', '', price_text).replace(',', '.')) if price_text else 0.0

            # Brand
            brand_elem = soup.find(class_=re.compile('brand|productBrand', re.I))
            brand = brand_elem.get_text(strip=True) if brand_elem else ''

            # Product ID from URL
            product_id = url.rstrip('/p').split('-')[-1]
            if not product_id.isdigit():
                product_id = '0'

            # Image
            img_elem = soup.find('img', class_=re.compile('productImage|product-image', re.I))
            image_url = img_elem.get('src', '') if img_elem else ''

            # Build product dict
            product = {
                'productId': product_id,
                'productName': product_name,
                'brand': brand,
                'linkText': url.split('/')[-2] if '/' in url else '',
                'productReference': '',
                'categoryId': None,
                'categories': [],
                'link': url,
                'description': '',
                'items': [{
                    'itemId': product_id,
                    'name': product_name,
                    'ean': '',
                    'variations': [],
                    'sellers': [{
                        'sellerId': '1',
                        'sellerName': 'Angeloni',
                        'addToCartLink': '',
                        'sellerDefault': True,
                        'commertialOffer': {
                            'Price': price,
                            'ListPrice': price,
                            'PriceWithoutDiscount': price,
                            'AvailableQuantity': 100,
                            'IsAvailable': price > 0,
                        }
                    }],
                    'images': [
                        {
                            'imageId': '1',
                            'imageUrl': image_url,
                            'imageLabel': '',
                            'imageText': product_name
                        }
                    ] if image_url else [],
                }],
            }

            # Only return if we got at least name and price
            if product_name and price > 0:
                return product

            return None

        except Exception as e:
            logger.error(f"HTML extraction failed: {e}")
            return None

    def _extract_from_javascript(self, html: str, url: str) -> Optional[Dict[str, Any]]:
        """Extract product data from JavaScript variables (__RUNTIME__, vtex.*, etc.)."""
        # This is a fallback strategy if HTML parsing fails
        # Implementation can be added later based on actual page structure
        return None

    def scrape_batch(
        self,
        product_urls: List[str],
        region_key: str,
        batch_number: int,
        metrics: Any
    ) -> List[Dict[str, Any]]:
        """
        Scrape a batch of product URLs.

        Returns:
            List of validated product dicts
        """
        validated_products = []

        with metrics.track_batch(batch_number, region=region_key) as batch:
            for url in product_urls:
                product = self.scrape_product_page(url)
                if product:
                    # Validate with Pydantic
                    try:
                        validated = VTEXProduct.parse_obj(product)
                        validated_products.append(validated.dict())
                    except ValidationError as e:
                        logger.warning(f"Validation failed for {url}: {e}")
                        self.validation_errors_count += 1

                time.sleep(self.request_delay)

            batch.products_count = len(validated_products)
            batch.success = True

        return validated_products

    def scrape_region(self, region_key: str, product_urls: List[str]):
        """
        Scrape Angeloni for a specific region using HTML scraping.

        Args:
            region_key: Region identifier (e.g., 'florianopolis_centro')
            product_urls: List of product URLs to scrape (from discover_products)
        """
        logger.info(f"[{self.store_name}/{region_key}] Starting HTML-based scrape")

        if not product_urls:
            logger.error("No product URLs provided")
            return

        # Setup output paths
        base_path = self.get_output_path(region_key)
        batches_dir = base_path / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)
        final_file = base_path / f"{self.store_name}_{region_key}_full.parquet"

        # Metrics
        metrics = get_metrics_collector(
            db_path=f"data/metrics/{self.store_name}_runs.duckdb",
            store_name=self.store_name
        )

        # Scrape in batches
        all_products = []
        for i in range(0, len(product_urls), self.batch_size):
            chunk = product_urls[i : i + self.batch_size]
            batch_number = i // self.batch_size

            logger.info(f"  Batch {batch_number}: {len(chunk)} products")
            products = self.scrape_batch(chunk, region_key, batch_number, metrics)

            if products:
                # Save batch
                batch_file = batches_dir / f"batch_{batch_number:05d}.parquet"
                self.save_batch(products, batch_file, region_key)
                all_products.extend(products)

            if i % 500 == 0 and i > 0:
                logger.info(f"  Progress: {i}/{len(product_urls)}")

        # Consolidate batches
        self.consolidate_batches(batches_dir, final_file)
        self.validate_run(region_key, final_file)

        logger.info(
            f"[{self.store_name}/{region_key}] Scrape complete: "
            f"{len(all_products)} products, "
            f"{self.validation_errors_count} validation errors"
        )
