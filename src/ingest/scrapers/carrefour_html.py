"""
Carrefour HTML Scraper.

Carrefour blocks VTEX API access (returns 503), so we scrape product pages directly.
Uses sitemap for discovery, then fetches HTML pages and parses JSON-LD structured data.

Optimizations:
- Async HTTP with aiohttp for parallel requests (10-20x faster)
- Connection pooling with persistent sessions
- URL validation cache to skip known 404s
- Larger batch sizes (100-200 products)
"""

import json
import time
import asyncio
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger
from bs4 import BeautifulSoup
import pandas as pd
from pydantic import ValidationError
import aiohttp

from .base import BaseScraper
from src.schemas.vtex import VTEXProduct
from src.observability.metrics import get_metrics_collector


class CarrefourHTMLScraper(BaseScraper):
    """
    HTML-based scraper for Carrefour (VTEX platform with blocked API).

    Discovery: Sitemaps (same as VTEX)
    Scraping: Direct HTML parsing with JSON-LD extraction
    """

    def __init__(self, store_name: str, config: dict):
        super().__init__(store_name, config)
        self.sitemap_pattern = config.get("sitemap_pattern", "/sitemap/product-{n}.xml")
        self.sitemap_start_index = config.get("sitemap_start_index", 0)
        self.validation_errors_count = 0

        # Async optimization settings
        self.max_concurrent_requests = config.get("max_concurrent_requests", 20)
        self.async_batch_size = config.get("async_batch_size", 100)

        # URL validation cache (skip known 404s)
        # Cache expires after 7 days (products may become available again)
        self.failed_urls_file = Path(f"data/cache/{store_name}_failed_urls.jsonl")
        self.cache_ttl_days = config.get("cache_ttl_days", 7)  # Default: 7 days

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

        This method filters products based on their last modification date,
        significantly reducing scrape time for daily/weekly incremental updates.

        Args:
            days_back: Only include products modified in last N days (default: 7)
            limit: Max products to return (optional)

        Returns:
            List of product URLs modified in the specified timeframe

        Example:
            # Daily incremental: last 1 day
            urls = scraper.discover_products_incremental(days_back=1)

            # Weekly incremental: last 7 days
            urls = scraper.discover_products_incremental(days_back=7)
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
                    # Reached end of sitemaps
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
                                # Invalid date format, include it to be safe
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

    def discover_new_products(
        self,
        previous_run_file: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[str]:
        """
        Discover only products not present in previous run (new arrivals).

        This method compares current sitemap with a previous run's data,
        returning only URLs not seen before. Useful for incremental scraping
        when sitemap lastmod is not maintained (like Carrefour).

        Args:
            previous_run_file: Path to previous run parquet file (optional)
                              If None, tries to find most recent run automatically
            limit: Max products to return (optional)

        Returns:
            List of new product URLs

        Example:
            # Auto-detect previous run
            urls = scraper.discover_new_products()

            # Specific previous file
            urls = scraper.discover_new_products(
                previous_run_file='data/bronze/.../carrefour_full.parquet'
            )
        """
        import pandas as pd
        from pathlib import Path

        # Find previous run file if not specified
        if previous_run_file is None:
            bronze_path = Path("data/bronze")
            store_path = bronze_path / f"supermarket={self.store_name}"

            if store_path.exists():
                parquet_files = list(store_path.rglob("*_full.parquet"))
                if parquet_files:
                    # Get most recent
                    previous_run_file = str(max(parquet_files, key=lambda p: p.stat().st_mtime))
                    logger.info(f"[{self.store_name}] Using previous run: {previous_run_file}")

        if not previous_run_file or not Path(previous_run_file).exists():
            logger.warning(
                f"[{self.store_name}] No previous run found. "
                f"Falling back to full discovery."
            )
            return self.discover_products(limit=limit)

        # Load previous URLs
        try:
            df_prev = pd.read_parquet(previous_run_file)
            previous_urls = set(df_prev['link'].unique())
            logger.info(
                f"[{self.store_name}] Previous run had {len(previous_urls):,} products"
            )
        except Exception as e:
            logger.error(f"Failed to load previous run: {e}")
            return self.discover_products(limit=limit)

        # Discover all current products
        logger.info(f"[{self.store_name}] Discovering current products...")
        all_products = self.discover_products(limit=None)

        # Filter new ones
        new_products = [url for url in all_products if url not in previous_urls]

        logger.info(
            f"[{self.store_name}] Found {len(new_products):,} new products "
            f"({len(new_products)/len(all_products)*100:.1f}% of catalog)"
        )

        return new_products[:limit] if limit else new_products

    def discover_sample(
        self,
        sample_rate: float = 0.1,
        priority_patterns: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[str]:
        """
        Discover products using sampling strategy for quick daily checks.

        Combines priority categories (always scraped) with random sampling
        of other products. Good for monitoring trends without full scrapes.

        Args:
            sample_rate: Sampling rate for non-priority products (0.1 = 10%)
            priority_patterns: URL patterns for high-priority categories
                              Default: fresh food, promotions
            limit: Max products to return (optional)

        Returns:
            List of sampled product URLs

        Example:
            # Daily monitoring: 10% sample + priority categories
            urls = scraper.discover_sample(sample_rate=0.1)

            # Quick check: 5% sample
            urls = scraper.discover_sample(sample_rate=0.05)
        """
        import random

        if priority_patterns is None:
            priority_patterns = [
                '/hortifruti/',
                '/acougue-e-peixaria/',
                '/frios-e-laticinios/',
                '/ofertas/',
                '/promocao/',
            ]

        logger.info(
            f"[{self.store_name}] Discovering products "
            f"(priority categories + {sample_rate*100:.0f}% sample)"
        )

        all_products = self.discover_products()

        priority = []
        others = []

        for url in all_products:
            if any(pattern in url for pattern in priority_patterns):
                priority.append(url)
            else:
                others.append(url)

        # Sample non-priority
        sample_count = int(len(others) * sample_rate)
        sampled = random.sample(others, min(sample_count, len(others)))

        selected = priority + sampled

        logger.info(
            f"[{self.store_name}] Selected {len(priority):,} priority + "
            f"{len(sampled):,} sampled = {len(selected):,} total "
            f"({len(selected)/len(all_products)*100:.1f}% of catalog)"
        )

        return selected[:limit] if limit else selected

    async def scrape_product_page_async(
        self,
        session: aiohttp.ClientSession,
        url: str
    ) -> Optional[Dict[str, Any]]:
        """
        Async version: Scrape a single product page and extract JSON-LD data.

        Returns:
            Product dict compatible with VTEXProduct schema, or None if failed
        """
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    if resp.status == 404:
                        # Cache 404s to skip them next time
                        self._cache_failed_url(url)
                    return None

                html = await resp.text()

            # Parse HTML
            soup = BeautifulSoup(html, 'html.parser')

            # Find JSON-LD structured data
            script = soup.find('script', type='application/ld+json')
            if not script or not script.string:
                return None

            data = json.loads(script.string)
            if data.get('@type') != 'Product':
                return None

            # Extract product data
            offer = data.get('offers', {})

            # Parse product ID from URL (format: /product-name-{id}/p)
            product_id = url.rstrip('/p').split('-')[-1]
            if not product_id.isdigit():
                # Alternative: use SKU
                product_id = str(data.get('sku', '0'))

            # Build VTEX-compatible product dict
            product = {
                'productId': product_id,
                'productName': data.get('name', ''),
                'brand': data.get('brand', {}).get('name', '') if isinstance(data.get('brand'), dict) else str(data.get('brand', '')),
                'linkText': url.split('/')[-2] if '/' in url else '',
                'productReference': data.get('mpn', ''),
                'categoryId': None,  # Not available in JSON-LD
                'categories': [data.get('category', '')] if data.get('category') else [],
                'link': url,
                'description': data.get('description', ''),
                'items': [{
                    'itemId': product_id,
                    'name': data.get('name', ''),
                    'ean': data.get('gtin', ''),
                    'variations': [],
                    'sellers': [{
                        'sellerId': '1',
                        'sellerName': 'Carrefour',
                        'addToCartLink': '',
                        'sellerDefault': True,
                        'commertialOffer': {
                            'Price': offer.get('price', 0),
                            'ListPrice': offer.get('price', 0),  # No list price in JSON-LD
                            'PriceWithoutDiscount': offer.get('price', 0),
                            'AvailableQuantity': 100 if 'InStock' in offer.get('availability', '') else 0,
                            'IsAvailable': 'InStock' in offer.get('availability', ''),
                        }
                    }],
                    'images': [
                        {
                            'imageId': '1',
                            'imageUrl': data.get('image', ''),
                            'imageLabel': '',
                            'imageText': data.get('name', '')
                        }
                    ] if data.get('image') else [],
                }],
            }

            return product

        except asyncio.TimeoutError:
            return None
        except json.JSONDecodeError:
            return None
        except Exception:
            return None

    def scrape_product_page(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Sync version: Scrape a single product page (kept for compatibility).

        Returns:
            Product dict compatible with VTEXProduct schema, or None if failed
        """
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                if resp.status_code == 404:
                    self._cache_failed_url(url)
                logger.warning(f"Failed to fetch {url}: HTTP {resp.status_code}")
                return None

            # Parse HTML
            soup = BeautifulSoup(resp.content, 'html.parser')

            # Find JSON-LD structured data
            script = soup.find('script', type='application/ld+json')
            if not script or not script.string:
                logger.warning(f"No JSON-LD found in {url}")
                return None

            data = json.loads(script.string)
            if data.get('@type') != 'Product':
                logger.warning(f"JSON-LD is not a Product: {url}")
                return None

            # Extract product data
            offer = data.get('offers', {})

            # Parse product ID from URL (format: /product-name-{id}/p)
            product_id = url.rstrip('/p').split('-')[-1]
            if not product_id.isdigit():
                # Alternative: use SKU
                product_id = str(data.get('sku', '0'))

            # Build VTEX-compatible product dict
            product = {
                'productId': product_id,
                'productName': data.get('name', ''),
                'brand': data.get('brand', {}).get('name', '') if isinstance(data.get('brand'), dict) else str(data.get('brand', '')),
                'linkText': url.split('/')[-2] if '/' in url else '',
                'productReference': data.get('mpn', ''),
                'categoryId': None,  # Not available in JSON-LD
                'categories': [data.get('category', '')] if data.get('category') else [],
                'link': url,
                'description': data.get('description', ''),
                'items': [{
                    'itemId': product_id,
                    'name': data.get('name', ''),
                    'ean': data.get('gtin', ''),
                    'variations': [],
                    'sellers': [{
                        'sellerId': '1',
                        'sellerName': 'Carrefour',
                        'addToCartLink': '',
                        'sellerDefault': True,
                        'commertialOffer': {
                            'Price': offer.get('price', 0),
                            'ListPrice': offer.get('price', 0),  # No list price in JSON-LD
                            'PriceWithoutDiscount': offer.get('price', 0),
                            'AvailableQuantity': 100 if 'InStock' in offer.get('availability', '') else 0,
                            'IsAvailable': 'InStock' in offer.get('availability', ''),
                        }
                    }],
                    'images': [
                        {
                            'imageId': '1',
                            'imageUrl': data.get('image', ''),
                            'imageLabel': '',
                            'imageText': data.get('name', '')
                        }
                    ] if data.get('image') else [],
                }],
            }

            return product

        except json.JSONDecodeError as e:
            logger.error(f"JSON-LD parse error in {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None

    def _cache_failed_url(self, url: str):
        """
        Cache a failed URL (404) with timestamp.

        Cache format (JSONL):
        {"url": "https://...", "failed_at": "2026-02-08T10:30:00", "status": 404}
        """
        from datetime import datetime

        cache_entry = {
            "url": url,
            "failed_at": datetime.now().isoformat(),
            "status": 404
        }

        with open(self.failed_urls_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(cache_entry) + "\n")

    def _load_failed_urls(self) -> set:
        """
        Load cached failed URLs that haven't expired yet.

        Cache TTL: Only URLs failed in the last N days are considered.
        This allows products to be re-checked periodically (e.g., out-of-stock items
        that come back, seasonal products, etc.)

        Returns:
            Set of URLs that are still considered failed (within TTL window)
        """
        from datetime import datetime, timedelta

        if not self.failed_urls_file.exists():
            return set()

        cutoff_date = datetime.now() - timedelta(days=self.cache_ttl_days)
        failed_urls = set()
        expired_count = 0

        # Read cache entries
        cache_entries = []
        try:
            with open(self.failed_urls_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        failed_at = datetime.fromisoformat(entry['failed_at'])

                        # Check if entry is still valid (within TTL)
                        if failed_at >= cutoff_date:
                            failed_urls.add(entry['url'])
                            cache_entries.append(entry)
                        else:
                            expired_count += 1
                    except (json.JSONDecodeError, KeyError, ValueError):
                        # Skip malformed entries
                        continue

            # Clean up expired entries (rewrite cache file)
            if expired_count > 0:
                logger.debug(
                    f"Cleaning cache: {expired_count} expired entries "
                    f"(older than {self.cache_ttl_days} days)"
                )
                with open(self.failed_urls_file, 'w', encoding='utf-8') as f:
                    for entry in cache_entries:
                        f.write(json.dumps(entry) + "\n")

        except Exception as e:
            logger.warning(f"Failed to load URL cache: {e}")
            return set()

        return failed_urls

    def _filter_known_failures(self, urls: List[str]) -> List[str]:
        """
        Filter out URLs that are known to fail (404) within cache TTL window.

        Note: Cache automatically expires after N days, so products that were
        temporarily unavailable will be re-checked eventually.
        """
        failed = self._load_failed_urls()
        if not failed:
            return urls

        filtered = [url for url in urls if url not in failed]
        skipped = len(urls) - len(filtered)

        if skipped > 0:
            logger.info(
                f"  Skipping {skipped:,} known failed URLs "
                f"(cached 404s from last {self.cache_ttl_days} days)"
            )

        return filtered

    def clear_cache(self):
        """
        Clear the failed URLs cache.

        Use this to force re-checking all products (e.g., after a major catalog update).

        Example:
            scraper.clear_cache()
        """
        if self.failed_urls_file.exists():
            self.failed_urls_file.unlink()
            logger.info(f"Cache cleared: {self.failed_urls_file}")
        else:
            logger.info("Cache already empty")

    async def scrape_batch_async(
        self,
        product_urls: List[str],
        region_key: str,
        batch_number: int,
        metrics: Any
    ) -> List[Dict[str, Any]]:
        """
        Async version: Scrape a batch of product URLs in parallel.

        Returns:
            List of validated product dicts
        """
        validated_products = []

        # Create aiohttp session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent_requests,
            limit_per_host=self.max_concurrent_requests,
            ttl_dns_cache=300
        )

        timeout = aiohttp.ClientTimeout(total=30, connect=10)

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml"
            }
        ) as session:
            # Create tasks for all URLs
            tasks = [
                self.scrape_product_page_async(session, url)
                for url in product_urls
            ]

            # Execute in parallel with progress tracking
            with metrics.track_batch(batch_number, region=region_key) as batch:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for url, product in zip(product_urls, results):
                    if isinstance(product, Exception):
                        continue

                    if product:
                        # Validate with Pydantic
                        try:
                            validated = VTEXProduct.parse_obj(product)
                            validated_products.append(validated.dict())
                        except ValidationError:
                            self.validation_errors_count += 1

                batch.products_count = len(validated_products)
                batch.success = True

        return validated_products

    def scrape_batch(
        self,
        product_urls: List[str],
        region_key: str,
        batch_number: int,
        metrics: Any
    ) -> List[Dict[str, Any]]:
        """
        Scrape a batch of product URLs (sync wrapper for async method).

        Returns:
            List of validated product dicts
        """
        # Use async version if asyncio event loop is available
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context, use sync version
                return self._scrape_batch_sync(product_urls, region_key, batch_number, metrics)
            else:
                # Run async version
                return loop.run_until_complete(
                    self.scrape_batch_async(product_urls, region_key, batch_number, metrics)
                )
        except RuntimeError:
            # No event loop, create new one
            return asyncio.run(
                self.scrape_batch_async(product_urls, region_key, batch_number, metrics)
            )

    def _scrape_batch_sync(
        self,
        product_urls: List[str],
        region_key: str,
        batch_number: int,
        metrics: Any
    ) -> List[Dict[str, Any]]:
        """Sync fallback version of scrape_batch."""
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
        Scrape Carrefour for a specific region using async HTML scraping.

        Args:
            region_key: Region identifier (e.g., 'florianopolis_centro')
            product_urls: List of product URLs to scrape (from discover_products)

        Note: Region-specific pricing may not work properly without VTEX segment cookies.

        Optimizations:
        - Filters out known failed URLs (cached 404s)
        - Uses async batch scraping with connection pooling
        - Larger batch size (100 instead of 50)
        """
        logger.info(f"[{self.store_name}/{region_key}] Starting optimized async scrape")

        if not product_urls:
            logger.error("No product URLs provided")
            return

        # Filter out known failed URLs
        product_urls = self._filter_known_failures(product_urls)

        logger.info(f"[{self.store_name}/{region_key}] Scraping {len(product_urls):,} products")

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

        # Use optimized batch size for async scraping
        batch_size = self.async_batch_size

        # Scrape in batches
        all_products = []
        total_batches = (len(product_urls) + batch_size - 1) // batch_size

        for i in range(0, len(product_urls), batch_size):
            chunk = product_urls[i : i + batch_size]
            batch_number = i // batch_size

            logger.info(
                f"  [{batch_number+1}/{total_batches}] Processing {len(chunk)} products "
                f"({i+len(chunk)}/{len(product_urls)})"
            )

            products = self.scrape_batch(chunk, region_key, batch_number, metrics)

            if products:
                # Save batch
                batch_file = batches_dir / f"batch_{batch_number:05d}.parquet"
                self.save_batch(products, batch_file, region_key)
                all_products.extend(products)

                success_rate = len(products) / len(chunk) * 100
                logger.info(f"    ✓ {len(products)} products scraped ({success_rate:.1f}% success rate)")

        # Consolidate batches
        self.consolidate_batches(batches_dir, final_file)
        self.validate_run(region_key, final_file)

        logger.info(
            f"[{self.store_name}/{region_key}] Scrape complete: "
            f"{len(all_products):,} products, "
            f"{self.validation_errors_count} validation errors"
        )
