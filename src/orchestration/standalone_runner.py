"""
Standalone scraper runner - Runs without Prefect

This script runs the scraper flow without requiring Prefect server.
Perfect for simple execution via Windows Task Scheduler or manual runs.

Usage:
    # Incremental (default - fast)
    python run_scraper_standalone.py

    # Full catalog
    python run_scraper_standalone.py --full

    # Specific stores
    python run_scraper_standalone.py --stores angeloni bistek

    # Custom incremental days
    python run_scraper_standalone.py --days 14
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
import argparse

def run_scraper_cli(stores=None, use_incremental=True, incremental_days=7):
    """
    Run scraper using CLI directly (no Prefect dependency).

    Args:
        stores: List of store names or None for all
        use_incremental: Use incremental mode (faster)
        incremental_days: Days to look back for incremental
    """
    project_root = Path(__file__).parent

    print("=" * 70)
    mode = "INCREMENTAL" if use_incremental else "FULL CATALOG"
    print(f"  Market Scraper - {mode} Mode")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Default stores (all active)
    if not stores:
        stores = ["bistek", "fort", "giassi", "carrefour", "angeloni", "superkoch"]

    print(f"Stores to scrape: {', '.join(stores)}")
    print(f"Mode: {mode}")
    if use_incremental:
        print(f"Incremental period: Last {incremental_days} days")
        print(f"Expected time: ~30-60 min per store")
    else:
        print(f"Expected time: ~2-8h per store")
    print()
    print("=" * 70)
    print()

    results = []
    for store in stores:
        print(f"\n{'='*70}")
        print(f"  Scraping: {store.upper()}")
        print(f"{'='*70}\n")

        # Build command
        cmd = [sys.executable, "scripts/cli.py", "scrape", store]

        if use_incremental:
            cmd.extend(["--incremental", str(incremental_days)])

        # Run scraper
        try:
            result = subprocess.run(
                cmd,
                cwd=project_root,
                capture_output=False,  # Show output in real-time
                text=True
            )

            success = result.returncode == 0
            results.append({
                'store': store,
                'success': success,
                'exit_code': result.returncode
            })

            if success:
                print(f"\n✅ {store} completed successfully!")
            else:
                print(f"\n❌ {store} failed with exit code {result.returncode}")

        except Exception as e:
            print(f"\n❌ {store} failed with error: {e}")
            results.append({
                'store': store,
                'success': False,
                'error': str(e)
            })

    # Summary
    print("\n" + "=" * 70)
    print("  SCRAPING SUMMARY")
    print("=" * 70)
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    successful = sum(1 for r in results if r.get('success'))
    failed = len(results) - successful

    print(f"✅ Successful: {successful}/{len(results)}")
    print(f"❌ Failed: {failed}/{len(results)}")

    if use_incremental:
        print(f"⚡ Time saved: ~85% compared to full scraping!")

    print("=" * 70)
    print()

    # Exit with error if any failed
    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run market scraper without Prefect"
    )
    parser.add_argument(
        "--stores",
        nargs="+",
        help="List of stores to scrape (default: all)",
        default=None
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Use full catalog mode (default: incremental)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Days to look back for incremental (default: 7)"
    )

    args = parser.parse_args()

    run_scraper_cli(
        stores=args.stores,
        use_incremental=not args.full,
        incremental_days=args.days
    )