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
@click.option('--csv', 'csv_path', type=click.Path(exists=True), help='Path to OpenFoodFacts CSV file')
@click.option('--parquet', 'parquet_path', type=click.Path(exists=True), help='Path to OpenFoodFacts Parquet file')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def bulk_import(csv_path, parquet_path, verbose):
    """
    Import OpenFoodFacts data from bulk download (CSV or Parquet).

    Download options:
    - Parquet (recommended): https://huggingface.co/datasets/openfoodfacts/product-database
    - CSV: https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz

    This command:
    1. Extracts EANs from tru_product (VTEX data)
    2. Filters bulk file to only include those EANs (fast DuckDB query)
    3. Validates and saves to bronze layer
    4. Updates watermark

    Examples:
        # Parquet (faster, recommended)
        python cli_enrich.py bulk-import --parquet data/external/openfoodfacts-food.parquet

        # CSV
        python cli_enrich.py bulk-import --csv data/external/en.openfoodfacts.org.products.csv.gz
    """
    import duckdb
    import pandas as pd
    from pathlib import Path

    # Validate input
    if not csv_path and not parquet_path:
        click.echo("Error: Must provide either --csv or --parquet")
        return
    if csv_path and parquet_path:
        click.echo("Error: Cannot use both --csv and --parquet")
        return

    input_path = csv_path or parquet_path
    is_parquet = parquet_path is not None

    run_id = f"openfoodfacts_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Setup logging
    from src.observability.logging_config import setup_logging
    setup_logging(
        run_id=run_id,
        store="openfoodfacts",
        region="global",
        verbose=verbose
    )

    logger.info(f"Starting bulk {'Parquet' if is_parquet else 'CSV'} import (run_id={run_id})")
    click.echo(f"Input file: {input_path}")

    # Initialize pipeline and watermark
    pipeline = EANEnrichmentPipeline()
    watermark = EANWatermark()

    # Step 1: Extract unique EANs from tru_product
    click.echo("Step 1/4: Extracting EANs from tru_product...")
    all_eans = pipeline.extract_unique_eans()
    click.echo(f"  Found {len(all_eans):,} unique EANs in VTEX data")

    # Step 2: Filter file with DuckDB (memory efficient)
    click.echo(f"Step 2/4: Filtering {'Parquet' if is_parquet else 'CSV'} for matching EANs (DuckDB)...")

    # Create temp DuckDB connection
    conn = duckdb.connect(':memory:')

    # Register EANs as table
    eans_df = pd.DataFrame({'ean': all_eans})
    conn.register('target_eans', eans_df)

    # Build query based on file format
    if is_parquet:
        # Parquet: Direct read with field extraction
        # Note: product_name is array of {lang, text}, extract first text
        query = f"""
            SELECT
                code,
                CASE
                    WHEN product_name IS NOT NULL AND len(product_name) > 0
                    THEN product_name[1]['text']
                    ELSE NULL
                END as product_name,
                brands,
                CASE
                    WHEN nutriscore_grade = 'unknown' THEN NULL
                    WHEN nutriscore_grade IN ('a', 'b', 'c', 'd', 'e') THEN nutriscore_grade
                    ELSE NULL
                END as nutriscore_grade
            FROM read_parquet('{input_path}')
            WHERE code IN (SELECT ean FROM target_eans)
                AND code IS NOT NULL
                AND length(code) IN (8, 13, 14)
        """
    else:
        # CSV: Tab-delimited with optional gzip
        csv_path_obj = Path(input_path)
        is_gzipped = csv_path_obj.suffix == '.gz'

        query = f"""
            SELECT
                code,
                product_name,
                brands,
                nutriscore_grade,
                categories,
                image_url
            FROM read_csv(
                '{input_path}',
                delim='\t',
                header=true,
                all_varchar=true,
                {'compression=''gzip''' if is_gzipped else ''}
            )
            WHERE code IN (SELECT ean FROM target_eans)
                AND code IS NOT NULL
                AND length(code) IN (8, 13, 14)
        """

    try:
        df_filtered = conn.execute(query).fetchdf()
        click.echo(f"  Found {len(df_filtered):,} matching products ({len(df_filtered)/len(all_eans)*100:.1f}% coverage)")
    except Exception as e:
        click.echo(f"  Error reading file: {e}")
        logger.error(f"File parsing failed: {e}")
        return
    finally:
        conn.close()

    if len(df_filtered) == 0:
        click.echo("  No matching products found in CSV. Nothing to import.")
        return

    # Step 3: Validate with Pydantic
    click.echo("Step 3/4: Validating products with Pydantic...")
    from src.schemas.openfoodfacts import OpenFoodFactsProduct

    products = []
    validation_errors = 0

    with click.progressbar(df_filtered.iterrows(), length=len(df_filtered), label='Validating') as bar:
        for _, row in bar:
            try:
                # Convert row to dict and validate
                product_dict = {
                    'code': row['code'],
                    'product_name': row['product_name'] if pd.notna(row['product_name']) else None,
                    'brands': row['brands'] if pd.notna(row['brands']) else None,
                    'nutriscore_grade': row['nutriscore_grade'] if pd.notna(row['nutriscore_grade']) else None,
                }

                product = OpenFoodFactsProduct.model_validate(product_dict)
                products.append(product.model_dump())
            except Exception as e:
                validation_errors += 1
                if verbose:
                    logger.warning(f"Validation error for EAN {row['code']}: {e}")

    click.echo(f"  Valid products: {len(products):,}")
    click.echo(f"  Validation errors: {validation_errors}")

    # Step 4: Save to bronze layer
    click.echo("Step 4/4: Saving to bronze layer...")
    if products:
        output_path = pipeline.save_to_bronze(products, run_id)
        click.echo(f"  Saved {len(products):,} products to {output_path}")
    else:
        click.echo("  No valid products to save")
        return

    # Update watermark
    watermark.save(all_eans)
    click.echo(f"  Updated watermark: {len(all_eans):,} EANs tracked")

    # Display final statistics
    click.echo("\n" + "="*50)
    click.echo("BULK IMPORT STATISTICS")
    click.echo("="*50)
    click.echo(f"Total EANs in VTEX:      {len(all_eans):,}")
    click.echo(f"Products found in CSV:   {len(df_filtered):,}")
    click.echo(f"Valid products saved:    {len(products):,}")
    click.echo(f"Validation errors:       {validation_errors}")
    click.echo(f"Coverage rate:           {len(products)/len(all_eans)*100:.1f}%")
    click.echo("="*50)

    logger.info(f"Bulk import complete: {len(products)} products imported")


@cli.command()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def delta_sync(verbose):
    """
    Sync OpenFoodFacts delta updates (last 14 days of changes).

    This command:
    1. Fetches delta index from OpenFoodFacts
    2. Downloads only new deltas (based on watermark timestamp)
    3. Processes changes for EANs in VTEX data
    4. Updates bronze layer incrementally

    Delta files cover ~14 days of product updates.
    Run this daily/weekly to keep data fresh.

    Example:
        python cli_enrich.py delta-sync
    """
    import requests
    import gzip
    import json
    import duckdb
    import pandas as pd
    from pathlib import Path
    from datetime import datetime as dt

    run_id = f"openfoodfacts_delta_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Setup logging
    setup_logging(
        run_id=run_id,
        store="openfoodfacts",
        region="global",
        verbose=verbose
    )

    logger.info(f"Starting delta sync (run_id={run_id})")
    click.echo("OpenFoodFacts Delta Sync")
    click.echo("="*50)

    # Initialize pipeline and watermark
    pipeline = EANEnrichmentPipeline()
    watermark = EANWatermark()

    # Step 1: Fetch delta index
    click.echo("Step 1/5: Fetching delta index...")
    try:
        response = requests.get("https://static.openfoodfacts.org/data/delta/index.txt", timeout=10)
        response.raise_for_status()
        delta_files = response.text.strip().split('\n')
        click.echo(f"  Found {len(delta_files)} delta files available")
    except Exception as e:
        click.echo(f"  Error fetching delta index: {e}")
        logger.error(f"Delta index fetch failed: {e}")
        return

    # Step 2: Parse timestamps and filter new deltas
    click.echo("Step 2/5: Checking for new deltas...")

    # Load delta watermark (last processed timestamp)
    delta_watermark_path = Path("data/metadata/delta_sync_watermark.json")
    if delta_watermark_path.exists():
        with open(delta_watermark_path, 'r') as f:
            delta_data = json.load(f)
            last_timestamp = delta_data.get('last_timestamp', 0)
            click.echo(f"  Last sync: {dt.fromtimestamp(last_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        last_timestamp = 0
        click.echo(f"  No previous sync found (first run)")

    # Parse delta filenames: openfoodfacts_products_[start]_[end].json.gz
    new_deltas = []
    for filename in delta_files:
        parts = filename.replace('openfoodfacts_products_', '').replace('.json.gz', '').split('_')
        if len(parts) == 2:
            start_ts, end_ts = int(parts[0]), int(parts[1])
            if end_ts > last_timestamp:
                new_deltas.append((filename, start_ts, end_ts))

    new_deltas.sort(key=lambda x: x[1])  # Sort by start timestamp

    if not new_deltas:
        click.echo(f"  No new deltas to process. Already up to date!")
        return

    click.echo(f"  Found {len(new_deltas)} new delta(s) to process")

    # Step 3: Extract EANs from VTEX
    click.echo("Step 3/5: Extracting EANs from tru_product...")
    all_eans = pipeline.extract_unique_eans()
    eans_set = set(all_eans)
    click.echo(f"  Target: {len(all_eans):,} unique EANs")

    # Step 4: Process each delta
    click.echo(f"Step 4/5: Processing {len(new_deltas)} delta file(s)...")

    total_products_updated = 0
    latest_timestamp = last_timestamp

    for filename, start_ts, end_ts in new_deltas:
        delta_url = f"https://static.openfoodfacts.org/data/delta/{filename}"
        click.echo(f"\n  Processing: {filename}")
        click.echo(f"    Period: {dt.fromtimestamp(start_ts).strftime('%Y-%m-%d')} to {dt.fromtimestamp(end_ts).strftime('%Y-%m-%d')}")

        try:
            # Download delta file
            response = requests.get(delta_url, timeout=30, stream=True)
            response.raise_for_status()

            # Decompress and parse JSON
            with gzip.open(response.raw, 'rt', encoding='utf-8') as f:
                products = []
                line_count = 0

                for line in f:
                    line_count += 1
                    try:
                        product_data = json.loads(line)

                        # Extract EAN code
                        code = product_data.get('code')
                        if not code or code not in eans_set:
                            continue

                        # Extract relevant fields (same as Parquet)
                        product_name_arr = product_data.get('product_name')
                        if isinstance(product_name_arr, list) and len(product_name_arr) > 0:
                            product_name = product_name_arr[0].get('text') if isinstance(product_name_arr[0], dict) else None
                        else:
                            product_name = product_name_arr if isinstance(product_name_arr, str) else None

                        nutriscore = product_data.get('nutriscore_grade')
                        if nutriscore == 'unknown':
                            nutriscore = None

                        products.append({
                            'code': code,
                            'product_name': product_name,
                            'brands': product_data.get('brands'),
                            'nutriscore_grade': nutriscore
                        })

                    except json.JSONDecodeError:
                        continue

                click.echo(f"    Scanned {line_count:,} products, found {len(products)} matches")

                # Save to bronze if we have updates
                if products:
                    from src.schemas.openfoodfacts import OpenFoodFactsProduct

                    valid_products = []
                    for prod in products:
                        try:
                            validated = OpenFoodFactsProduct.model_validate(prod)
                            valid_products.append(validated.model_dump())
                        except:
                            pass

                    if valid_products:
                        output_path = pipeline.save_to_bronze(valid_products, f"{run_id}_{end_ts}")
                        click.echo(f"    Saved {len(valid_products)} products to bronze")
                        total_products_updated += len(valid_products)

                # Update latest timestamp
                latest_timestamp = max(latest_timestamp, end_ts)

        except Exception as e:
            click.echo(f"    Error processing delta: {e}")
            logger.error(f"Delta processing failed: {e}")
            continue

    # Step 5: Update delta watermark
    click.echo(f"\nStep 5/5: Updating delta watermark...")
    delta_watermark_path.parent.mkdir(parents=True, exist_ok=True)
    with open(delta_watermark_path, 'w') as f:
        json.dump({
            'last_timestamp': latest_timestamp,
            'last_sync_date': dt.fromtimestamp(latest_timestamp).isoformat(),
            'run_id': run_id
        }, f, indent=2)

    click.echo(f"  Watermark updated: {dt.fromtimestamp(latest_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")

    # Display final statistics
    click.echo("\n" + "="*50)
    click.echo("DELTA SYNC STATISTICS")
    click.echo("="*50)
    click.echo(f"Deltas processed:        {len(new_deltas)}")
    click.echo(f"Products updated:        {total_products_updated}")
    click.echo(f"Latest timestamp:        {dt.fromtimestamp(latest_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    click.echo("="*50)

    logger.info(f"Delta sync complete: {total_products_updated} products updated")

    # Remind user to update DBT
    if total_products_updated > 0:
        click.echo("\nNext step: Update DBT models")
        click.echo("  cd src/transform/dbt_project")
        click.echo("  dbt run --select stg_openfoodfacts__products dim_ean")


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
