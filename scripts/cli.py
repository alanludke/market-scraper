"""
Market Scraper CLI - single entry point for all operations.

Usage:
    python cli.py scrape bistek                     # all regions
    python cli.py scrape bistek --region floripa     # specific region
    python cli.py scrape bistek --limit 100          # test with limit
    python cli.py scrape --all                       # all stores

    python cli.py list-stores                        # show available stores
    python cli.py list-regions bistek                 # show regions for store

    python cli.py report                             # generate Excel report
    python cli.py query "SELECT * FROM silver LIMIT 5"  # DuckDB query

    python cli.py upload bistek                      # upload latest run to Azure Blob
"""

import argparse
import sys
import yaml
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

from src.ingest.scrapers import SCRAPER_REGISTRY
from src.observability.logging_config import setup_logging


def load_config() -> dict:
    config_path = Path(__file__).parent / "config" / "stores.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


PLATFORM_MAP = {
    "vtex": "vtex",
}


def get_scraper(store_name: str, store_config: dict):
    platform = store_config.get("platform", "vtex")
    scraper_cls = SCRAPER_REGISTRY.get(PLATFORM_MAP.get(platform, platform))
    if not scraper_cls:
        raise ValueError(
            f"No scraper registered for platform '{platform}'. "
            f"Available: {list(SCRAPER_REGISTRY.keys())}"
        )
    return scraper_cls(store_name, store_config)


# ── Commands ────────────────────────────────────────────────

def cmd_scrape(args, config):
    stores = config["stores"]

    if args.all:
        targets = list(stores.keys())
    elif args.store:
        if args.store not in stores:
            print(f"Store '{args.store}' not found. Available: {list(stores.keys())}")
            sys.exit(1)
        targets = [args.store]
    else:
        print("Specify a store name or use --all")
        sys.exit(1)

    regions_filter = [args.region] if args.region else None

    if args.parallel and len(targets) > 1:
        with ThreadPoolExecutor(max_workers=min(4, len(targets))) as executor:
            futures = {}
            for store_name in targets:
                scraper = get_scraper(store_name, stores[store_name])
                futures[executor.submit(scraper.run, regions_filter, args.limit)] = store_name
            for future in as_completed(futures):
                store_name = futures[future]
                try:
                    future.result()
                    logger.info(f"[{store_name}] Done")
                except Exception as e:
                    logger.error(f"[{store_name}] Failed: {e}")
    else:
        for store_name in targets:
            scraper = get_scraper(store_name, stores[store_name])
            scraper.run(regions=regions_filter, limit=args.limit)


def cmd_list_stores(args, config):
    for name, cfg in config["stores"].items():
        n_regions = len(cfg.get("regions", {}))
        print(f"  {name:30s} ({cfg.get('platform', 'vtex')}, {n_regions} regions)")


def cmd_list_regions(args, config):
    stores = config["stores"]
    if args.store not in stores:
        print(f"Store '{args.store}' not found.")
        sys.exit(1)
    store = stores[args.store]
    print(f"\nRegions for {args.store} ({store['base_url']}):\n")
    for region_key, rcfg in store["regions"].items():
        hub = rcfg.get("hub_id") or "auto"
        print(f"  {region_key:35s}  CEP={rcfg['cep']}  SC={rcfg['sc']}  hub={hub[:20]}...")


def cmd_report(args, config):
    from src.analytics.reports import generate_reports
    generate_reports()


def cmd_query(args, config):
    from src.analytics.engine import MarketAnalytics
    db = MarketAnalytics()
    try:
        result = db.query(args.sql)
        print(result.to_string(index=False))
    except Exception as e:
        print(f"Query error: {e}")


def cmd_upload(args, config):
    from src.storage.azure_blob import BlobUploader
    uploader = BlobUploader()
    if args.store:
        uploader.upload_latest(args.store)
    else:
        for store_name in config["stores"]:
            uploader.upload_latest(store_name)


# ── Argument parser ─────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="market_scraper",
        description="Supermarket price scraping pipeline",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command")

    # scrape
    p_scrape = sub.add_parser("scrape", help="Run scrapers")
    p_scrape.add_argument("store", nargs="?", help="Store name (e.g. bistek)")
    p_scrape.add_argument("--all", action="store_true", help="Scrape all stores")
    p_scrape.add_argument("--region", type=str, help="Specific region key")
    p_scrape.add_argument("--limit", type=int, help="Max products (for testing)")
    p_scrape.add_argument("--parallel", action="store_true", help="Run stores in parallel")

    # list-stores
    sub.add_parser("list-stores", help="List configured stores")

    # list-regions
    p_regions = sub.add_parser("list-regions", help="List regions for a store")
    p_regions.add_argument("store", help="Store name")

    # report
    sub.add_parser("report", help="Generate Excel intelligence report")

    # query
    p_query = sub.add_parser("query", help="Run DuckDB SQL query")
    p_query.add_argument("sql", help="SQL query string")

    # upload
    p_upload = sub.add_parser("upload", help="Upload data to Azure Blob Storage")
    p_upload.add_argument("store", nargs="?", help="Store name (all if omitted)")

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Setup Loguru logging (will be overridden per scraper run with run_id)
    setup_logging(run_id="cli", store="cli", region="cli", verbose=args.verbose)
    config = load_config()

    commands = {
        "scrape": cmd_scrape,
        "list-stores": cmd_list_stores,
        "list-regions": cmd_list_regions,
        "report": cmd_report,
        "query": cmd_query,
        "upload": cmd_upload,
    }

    commands[args.command](args, config)
