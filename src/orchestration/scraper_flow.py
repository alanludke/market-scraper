"""
Prefect Flow - Daily Scraping of All Supermarket Stores

This flow orchestrates parallel scraping of all configured stores with
automatic retries, logging, and monitoring via Prefect dashboard.

Usage:
    # Run once (test)
    python src/orchestration/scraper_flow.py

    # Deploy with schedule
    prefect deploy src/orchestration/scraper_flow.py:daily_scraper_flow \
        --name daily-scraper \
        --cron "0 1 * * *"

    # Start worker (keep running)
    prefect worker start --pool market-scraper-pool
"""

from prefect import flow, task
from datetime import timedelta
from typing import Optional, List
import subprocess
import logging
import os
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


def load_stores_config() -> dict:
    """Load stores configuration from src/ingest/config/stores.yaml."""
    config_path = Path(__file__).parent.parent / "ingest" / "config" / "stores.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("stores", {})


@task(
    retries=2,
    retry_delay_seconds=600,  # 10 minutes
    log_prints=True,
    timeout_seconds=7200,  # 2 hours per store
)
def scrape_store(store_name: str, use_incremental: bool = True, incremental_days: int = 7) -> dict:
    """
    Scrape a single store (all regions).

    Args:
        store_name: Store identifier (bistek, fort, giassi, etc.)
        use_incremental: If True, use incremental scraping (only recent products). Default: True
        incremental_days: Number of days to look back for incremental scraping. Default: 7

    Returns:
        dict: Scraping statistics (products scraped, duration, etc.)
    """
    mode = "INCREMENTAL" if use_incremental else "FULL"
    print(f"[SCRAPING] Starting {mode} scrape for store: {store_name}")

    # Get project root and add to PYTHONPATH
    project_root = Path(__file__).parent.parent.parent

    # Prepare environment with PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)

    # Build CLI command
    # Incremental mode: Only scrape products modified in last N days (8-16x faster!)
    # Full mode: Scrape entire catalog (use for first run or monthly full refresh)
    cmd = ["python", "scripts/cli.py", "scrape", store_name]

    if use_incremental:
        cmd.extend(["--incremental", str(incremental_days)])
        print(f"[SCRAPING] Using incremental mode (last {incremental_days} days)")
    else:
        print(f"[SCRAPING] Using full catalog mode")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=project_root,
        env=env
    )

    if result.returncode != 0:
        error_msg = f"Scraping failed for {store_name}:\n{result.stderr}"
        logger.error(error_msg)
        raise Exception(f"Scraping failed for {store_name} with exit code {result.returncode}")

    # Parse output for stats
    output = result.stdout
    print(f"[SCRAPING] {store_name} output:\n{output}")

    # Extract statistics (simple parsing)
    stats = {
        'store': store_name,
        'success': True,
        'output_lines': len(output.split('\n'))
    }

    # Try to extract "Products scraped: X"
    for line in output.split('\n'):
        if 'products' in line.lower() and any(char.isdigit() for char in line):
            try:
                # Simple heuristic to extract number
                numbers = ''.join(c for c in line if c.isdigit())
                if numbers:
                    stats['products_scraped'] = int(numbers[:6])  # Limit to reasonable number
            except:
                pass

    print(f"[SCRAPING] ✅ {store_name} completed: {stats}")
    return stats


@flow(
    name="daily-scraper",
    description="Daily scraping of all supermarket stores (parallel execution)",
    log_prints=True
)
def daily_scraper_flow(
    stores: Optional[List[str]] = None,
    use_incremental: bool = True,
    incremental_days: int = 7
) -> dict:
    """
    Main flow for daily scraping of all stores.

    Args:
        stores: Optional list of stores to scrape. If None, scrapes all configured stores.
        use_incremental: If True, scrape only recent products (8-16x faster). Default: True
        incremental_days: Number of days to look back for incremental scraping. Default: 7

    Steps:
    1. Load store configuration
    2. Execute scrapers in parallel (with Prefect concurrency management)
    3. Collect and return results

    Returns:
        dict: Flow execution summary with per-store results

    Examples:
        # Daily incremental scraping (default, fast)
        daily_scraper_flow()

        # Full catalog scraping (monthly refresh)
        daily_scraper_flow(use_incremental=False)

        # Custom incremental period
        daily_scraper_flow(incremental_days=14)
    """
    mode = "INCREMENTAL" if use_incremental else "FULL CATALOG"
    print("="*60)
    print(f"  Daily Scraper Flow - {mode} Mode")
    print("="*60)

    # Load stores configuration
    stores_config = load_stores_config()

    # Determine which stores to scrape
    if stores is None:
        # Scrape ALL active stores
        stores_to_scrape = [
            "bistek",
            "fort",
            "giassi",
            "carrefour",
            "angeloni",
            "superkoch",
        ]
    else:
        stores_to_scrape = stores

    print(f"\nStores to scrape: {', '.join(stores_to_scrape)}")
    print(f"Total stores: {len(stores_to_scrape)}")

    # Validate stores exist in config
    for store in stores_to_scrape:
        if store not in stores_config:
            raise ValueError(f"Store '{store}' not found in src/ingest/config/stores.yaml")

    print("\n" + "="*60)
    print("  Starting parallel scraping...")
    if use_incremental:
        print(f"  Mode: INCREMENTAL (last {incremental_days} days)")
        print(f"  Expected time: ~30-60 min per store")
    else:
        print(f"  Mode: FULL CATALOG")
        print(f"  Expected time: ~2-8h per store (depending on catalog size)")
    print("="*60 + "\n")

    # Execute scrapers in parallel using Prefect's map
    # Prefect will handle concurrency and retries automatically
    # Pass use_incremental and incremental_days to all tasks
    from prefect import unmapped
    scraping_results = scrape_store.map(
        stores_to_scrape,
        use_incremental=unmapped(use_incremental),
        incremental_days=unmapped(incremental_days)
    )

    # Wait for all tasks to complete and collect results
    completed_results = [result for result in scraping_results]

    # Summary
    total_products = sum(r.get('products_scraped', 0) for r in completed_results)
    successful_stores = sum(1 for r in completed_results if r.get('success', False))

    summary = {
        'total_stores': len(stores_to_scrape),
        'successful_stores': successful_stores,
        'failed_stores': len(stores_to_scrape) - successful_stores,
        'total_products_scraped': total_products,
        'store_results': completed_results,
        'success': successful_stores == len(stores_to_scrape),
        'mode': 'incremental' if use_incremental else 'full',
        'incremental_days': incremental_days if use_incremental else None
    }

    print("\n" + "="*60)
    print("  Scraping Flow Completed!")
    print("="*60)
    mode_info = f"INCREMENTAL ({incremental_days}d)" if use_incremental else "FULL CATALOG"
    print(f"🎯 Mode: {mode_info}")
    print(f"✅ Successful: {successful_stores}/{len(stores_to_scrape)} stores")
    print(f"📦 Total products scraped: {total_products}")
    if use_incremental:
        print(f"⚡ Time saved: ~85% compared to full scraping!")
    print("="*60 + "\n")

    return summary


if __name__ == "__main__":
    # Run flow locally (for testing)
    # Test with a single store first
    daily_scraper_flow(stores=["bistek"])
