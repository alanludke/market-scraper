"""
Benchmark script to compare sync vs async scraper performance.

Tests a small sample (100-200 products) to measure:
- Time per product
- Success rate
- Overall speedup

Usage:
    python scripts/benchmark_async_scrapers.py carrefour
    python scripts/benchmark_async_scrapers.py angeloni
"""

import sys
import time
import yaml
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingest.scrapers import SCRAPER_REGISTRY
from loguru import logger


def load_config() -> dict:
    """Load stores configuration."""
    config_path = Path(__file__).parent.parent / "src" / "ingest" / "config" / "stores.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_scraper(store_name: str):
    """Get scraper instance for a store."""
    config = load_config()
    stores = config["stores"]

    if store_name not in stores:
        raise ValueError(f"Store '{store_name}' not found. Available: {list(stores.keys())}")

    store_config = stores[store_name]
    platform = store_config.get("platform", "vtex")

    scraper_cls = SCRAPER_REGISTRY.get(platform)
    if not scraper_cls:
        raise ValueError(
            f"No scraper registered for platform '{platform}'. "
            f"Available: {list(SCRAPER_REGISTRY.keys())}"
        )

    return scraper_cls(store_name, store_config)


def benchmark_scraper(store_name: str, sample_size: int = 100):
    """
    Benchmark a scraper with a small sample.

    Args:
        store_name: Store to benchmark (carrefour, angeloni)
        sample_size: Number of products to test (default: 100)
    """
    logger.info(f"=" * 80)
    logger.info(f"BENCHMARK: {store_name.upper()}")
    logger.info(f"=" * 80)

    # Get scraper
    scraper = get_scraper(store_name)

    # Discover products (limited sample)
    logger.info(f"Discovering {sample_size} product URLs...")
    start_discovery = time.time()
    product_urls = scraper.discover_products(limit=sample_size)
    discovery_time = time.time() - start_discovery

    logger.info(f"✓ Discovered {len(product_urls):,} URLs in {discovery_time:.1f}s")

    if len(product_urls) == 0:
        logger.error("No products discovered. Aborting benchmark.")
        return

    # Get first region
    region_key = list(scraper.regions.keys())[0]
    logger.info(f"Testing with region: {region_key}")

    # Setup paths
    base_path = scraper.get_output_path(region_key)
    batches_dir = base_path / "batches"
    batches_dir.mkdir(parents=True, exist_ok=True)

    # Import metrics
    from src.observability.metrics import get_metrics_collector
    metrics = get_metrics_collector(
        db_path=f"data/metrics/{store_name}_benchmark.duckdb",
        store_name=store_name
    )

    # Run scrape
    logger.info(f"Starting async scrape of {len(product_urls)} products...")
    start_scrape = time.time()

    all_products = []
    batch_size = getattr(scraper, 'async_batch_size', 100)

    for i in range(0, len(product_urls), batch_size):
        chunk = product_urls[i : i + batch_size]
        batch_number = i // batch_size

        logger.info(f"  Batch {batch_number}: {len(chunk)} products")
        products = scraper.scrape_batch(chunk, region_key, batch_number, metrics)

        if products:
            all_products.extend(products)
            batch_file = batches_dir / f"batch_{batch_number:05d}.parquet"
            scraper.save_batch(products, batch_file, region_key)

    scrape_time = time.time() - start_scrape

    # Results
    logger.info(f"=" * 80)
    logger.info(f"RESULTS:")
    logger.info(f"=" * 80)
    logger.info(f"Total products scraped: {len(all_products):,}")
    logger.info(f"Total time: {scrape_time:.1f}s")
    logger.info(f"Products per second: {len(all_products) / scrape_time:.2f}")
    logger.info(f"Seconds per product: {scrape_time / len(all_products):.2f}s")
    logger.info(f"Success rate: {len(all_products) / len(product_urls) * 100:.1f}%")
    logger.info(f"Validation errors: {scraper.validation_errors_count}")

    # Estimated full catalog time
    if store_name == 'carrefour':
        total_products = 65044
    elif store_name == 'angeloni':
        total_products = 15196
    else:
        total_products = len(product_urls) * 10  # Estimate

    estimated_hours = (total_products / len(all_products)) * scrape_time / 3600
    logger.info(f"")
    logger.info(f"Estimated time for full catalog ({total_products:,} products): {estimated_hours:.1f}h")

    logger.info(f"=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/benchmark_async_scrapers.py <store_name>")
        print("Example: python scripts/benchmark_async_scrapers.py carrefour")
        sys.exit(1)

    store = sys.argv[1].lower()
    sample = int(sys.argv[2]) if len(sys.argv) > 2 else 100

    benchmark_scraper(store, sample_size=sample)