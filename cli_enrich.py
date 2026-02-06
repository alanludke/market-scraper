"""
CLI for enriching VTEX products with OpenFoodFacts data.

Usage:
    python cli_enrich.py --limit 100        # Test with 100 EANs
    python cli_enrich.py --full             # Full enrichment (ignore watermark)
    python cli_enrich.py                    # Incremental enrichment (only new EANs)
"""

import click
from datetime import datetime
from loguru import logger

from src.enrichment.openfoodfacts import EANEnrichmentPipeline, EANWatermark
from src.observability.logging_config import setup_logging


@click.group()
def cli():
    """Market Scraper - Data Enrichment CLI."""
    pass


@cli.command()
@click.option('--limit', type=int, default=None, help='Limit number of EANs to enrich (for testing)')
@click.option('--full', is_flag=True, help='Full enrichment (ignore watermark, re-fetch all EANs)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def eans(limit, full, verbose):
    """
    Enrich EAN codes from VTEX products using OpenFoodFacts API.

    By default, only fetches new EANs not yet enriched (incremental mode).
    Use --full to re-fetch all EANs regardless of watermark.
    Use --limit to test with a subset of EANs.
    """
    run_id = f"openfoodfacts_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Setup logging
    setup_logging(
        run_id=run_id,
        store="openfoodfacts",
        region="global",
        verbose=verbose
    )

    logger.info(f"Starting EAN enrichment (run_id={run_id})")

    # Initialize pipeline and watermark
    pipeline = EANEnrichmentPipeline()
    watermark = EANWatermark()

    # Extract unique EANs from tru_product
    all_eans = pipeline.extract_unique_eans()
    click.echo(f"Found {len(all_eans)} unique EANs in tru_product")

    # Filter new EANs (unless --full)
    if full:
        click.echo("Full enrichment mode: fetching all EANs")
        eans_to_fetch = all_eans
    else:
        eans_to_fetch = watermark.get_new_eans(all_eans)
        click.echo(f"Incremental mode: {len(eans_to_fetch)} new EANs to enrich")

        if len(eans_to_fetch) == 0:
            click.echo("No new EANs to enrich. All EANs are up to date!")
            return

    # Apply limit (for testing)
    if limit:
        eans_to_fetch = eans_to_fetch[:limit]
        click.echo(f"Limited to {limit} EANs for testing")

    # Fetch from OpenFoodFacts API
    click.echo(f"Fetching {len(eans_to_fetch)} EANs from OpenFoodFacts API...")

    with click.progressbar(length=len(eans_to_fetch), label='Enriching EANs') as bar:
        products = []
        for idx, ean in enumerate(eans_to_fetch):
            if idx % 10 == 0:
                bar.update(10)

            with pipeline.rate_limiter.limit():
                url = f"{pipeline.BASE_URL}/product/{ean}.json"
                import requests
                response = requests.get(url, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 1:
                        try:
                            from src.schemas.openfoodfacts import OpenFoodFactsProduct
                            product = OpenFoodFactsProduct.model_validate(data['product'])
                            products.append(product.model_dump())
                            pipeline.stats["products_found"] += 1
                        except Exception:
                            pipeline.stats["validation_errors"] += 1
                    else:
                        pipeline.stats["products_not_found"] += 1

        # Update progress bar to 100%
        bar.update(len(eans_to_fetch) - (len(eans_to_fetch) // 10) * 10)

    # Save to bronze layer
    if products:
        output_path = pipeline.save_to_bronze(products, run_id)
        click.echo(f"Saved {len(products)} products to {output_path}")
    else:
        click.echo("No products found, nothing to save")

    # Update watermark
    watermark.save(all_eans)
    click.echo(f"Updated watermark: {len(all_eans)} EANs tracked")

    # Display statistics
    stats = pipeline.get_stats()
    click.echo("\n" + "="*50)
    click.echo("ENRICHMENT STATISTICS")
    click.echo("="*50)
    click.echo(f"Total EANs extracted:    {stats['eans_extracted']}")
    click.echo(f"EANs fetched from API:   {len(eans_to_fetch)}")
    click.echo(f"Products found:          {stats['products_found']}")
    click.echo(f"Products not found:      {stats['products_not_found']}")
    click.echo(f"Validation errors:       {stats['validation_errors']}")
    click.echo(f"API errors:              {stats['api_errors']}")
    click.echo(f"Success rate:            {stats['products_found']/len(eans_to_fetch)*100:.1f}%")
    click.echo("="*50)

    logger.info(f"Enrichment complete: {stats}")


@cli.command()
def stats():
    """Show current watermark statistics."""
    watermark = EANWatermark()
    stats = watermark.get_stats()

    click.echo("\n" + "="*50)
    click.echo("WATERMARK STATISTICS")
    click.echo("="*50)
    click.echo(f"Watermark file: {stats['path']}")
    click.echo(f"Exists: {stats['exists']}")
    click.echo(f"Enriched EANs: {stats['ean_count']}")
    click.echo("="*50)


if __name__ == '__main__':
    cli()
