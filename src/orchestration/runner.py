"""
Prefect Cloud Flow Runner - Simplified version without @task/@flow decorators

This runs directly via Prefect Cloud without needing local server.
Compatible with Free Tier using serve() instead of deploy.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Now import after path is set
import yaml


def load_stores_config() -> dict:
    """Load stores configuration."""
    config_path = project_root / "config" / "stores.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f).get("stores", {})


def run_scraper(
    stores: list[str] = None,
    use_incremental: bool = True,
    incremental_days: int = 7
):
    """
    Simple scraper runner for Prefect Cloud.

    Args:
        stores: List of store names (default: all)
        use_incremental: Use incremental mode
        incremental_days: Days to look back
    """
    print("=" * 70)
    mode = "INCREMENTAL" if use_incremental else "FULL CATALOG"
    print(f"  Market Scraper - {mode} Mode (Prefect Cloud)")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Default stores
    if not stores:
        stores = ["bistek", "fort", "giassi", "carrefour", "angeloni", "superkoch"]

    stores_config = load_stores_config()

    print(f"Stores: {', '.join(stores)}")
    print(f"Mode: {mode}")
    if use_incremental:
        print(f"Period: Last {incremental_days} days")
    print()

    results = []
    for store_name in stores:
        if store_name not in stores_config:
            print(f"❌ {store_name}: Not in config, skipping")
            continue

        print(f"\n{'='*70}")
        print(f"  Scraping: {store_name.upper()}")
        print(f"{'='*70}\n")

        try:
            # Call CLI directly
            from src.cli.scraper import main as cli_main
            import sys

            # Build args
            args = ["scrape", store_name]
            if use_incremental:
                args.extend(["--incremental", str(incremental_days)])

            # Backup original argv
            original_argv = sys.argv
            try:
                sys.argv = ["cli.py"] + args
                cli_main()
                success = True
            except SystemExit as e:
                success = e.code == 0
            finally:
                sys.argv = original_argv

            results.append({'store': store_name, 'success': success})

            if success:
                print(f"\n✅ {store_name} completed!")
            else:
                print(f"\n❌ {store_name} failed!")

        except Exception as e:
            print(f"\n❌ {store_name} error: {e}")
            results.append({'store': store_name, 'success': False})

    # Summary
    print(f"\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    successful = sum(1 for r in results if r['success'])
    print(f"\n✅ Successful: {successful}/{len(results)}")
    print(f"❌ Failed: {len(results) - successful}/{len(results)}")

    if use_incremental:
        print(f"⚡ Time saved: ~85% vs full scraping")

    print(f"{'='*70}\n")

    return {'successful': successful, 'total': len(results), 'results': results}


if __name__ == "__main__":
    # Can be run directly or served to Prefect Cloud
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--stores", nargs="+", default=None)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--serve", action="store_true", help="Serve to Prefect Cloud")

    args = parser.parse_args()

    if args.serve:
        # Serve to Prefect Cloud
        from prefect import flow, serve as prefect_serve

        # Wrap in flow decorator
        @flow(name="market-scraper-incremental", log_prints=True)
        def market_scraper_flow():
            return run_scraper(use_incremental=True, incremental_days=7)

        @flow(name="market-scraper-full", log_prints=True)
        def market_scraper_full_flow():
            return run_scraper(use_incremental=False)

        # Serve both flows
        print("=" * 70)
        print("  🚀 Serving flows to Prefect Cloud")
        print("=" * 70)
        print()
        print("Flows:")
        print("  ✅ market-scraper-incremental (daily 2 AM)")
        print("  ✅ market-scraper-full (monthly day 1, 3 AM)")
        print()
        print("Dashboard: https://app.prefect.cloud")
        print()
        print("⏳ Waiting for scheduled runs...")
        print("   (You can trigger manually from the dashboard)")
        print()
        print("=" * 70)
        print()

        prefect_serve(
            market_scraper_flow.to_deployment(
                name="daily-incremental",
                cron="0 2 * * *",  # 2 AM daily
                tags=["scraper", "incremental"]
            ),
            market_scraper_full_flow.to_deployment(
                name="monthly-full",
                cron="0 3 1 * *",  # 3 AM on 1st of month
                tags=["scraper", "full"]
            )
        )
    else:
        # Run directly
        run_scraper(
            stores=args.stores,
            use_incremental=not args.full,
            incremental_days=args.days
        )