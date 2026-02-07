"""
Prefect Flow - Daily Data Platform Pipeline (Main Orchestrator)

This is the MAIN orchestrator flow that coordinates the entire data platform
end-to-end, executing all steps in the correct order with dependencies.

Pipeline Steps:
    1. Ingestão     → Scrape all supermarket stores (parallel)
    2. Enriquecimento → OpenFoodFacts delta-sync
    3. Transformação  → DBT models (bronze → silver → gold)
    4. Disponibilização → Reports, dashboards, exports

Usage:
    # Run once (test)
    python src/orchestration/daily_pipeline_flow.py

    # Deploy with schedule (runs daily at 1:00 AM)
    prefect deploy src/orchestration/daily_pipeline_flow.py:daily_pipeline_flow \
        --name daily-pipeline \
        --cron "0 1 * * *"

    # Start worker (keep running)
    prefect worker start --pool market-scraper-pool
"""

from prefect import flow
from datetime import datetime
import logging

# Import all sub-flows
from src.orchestration.scraper_flow import daily_scraper_flow
from src.orchestration.delta_sync_flow import daily_delta_sync_flow
from src.orchestration.transform_flow import daily_transform_flow
from src.orchestration.analytics_flow import daily_analytics_flow

logger = logging.getLogger(__name__)


@flow(
    name="daily-pipeline",
    description="Daily end-to-end data platform pipeline (Ingestão → Transformação → Disponibilização)",
    log_prints=True
)
def daily_pipeline_flow(
    run_scraping: bool = True,
    run_enrichment: bool = True,
    run_transform: bool = True,
    run_analytics: bool = True,
    scrape_stores: list = None,
) -> dict:
    """
    Main orchestrator flow for the entire data platform.

    This flow coordinates all sub-flows in the correct order with proper
    dependencies, ensuring data flows smoothly from ingestion to analytics.

    Args:
        run_scraping: Execute scraping step (default: True)
        run_enrichment: Execute OpenFoodFacts enrichment (default: True)
        run_transform: Execute DBT transformations (default: True)
        run_analytics: Execute analytics and reporting (default: True)
        scrape_stores: Optional list of specific stores to scrape

    Pipeline Flow:
        1. INGESTÃO (1-3h)
           ├─ Scrape all supermarkets in parallel
           └─ Output: bronze/ parquet files

        2. ENRIQUECIMENTO (5-15min)
           ├─ OpenFoodFacts delta-sync
           └─ Output: enriched bronze/

        3. TRANSFORMAÇÃO (10-30min)
           ├─ DBT staging models
           ├─ DBT trusted models
           ├─ DBT marts models
           ├─ DBT tests (data quality)
           └─ Output: silver/, gold/ layers

        4. DISPONIBILIZAÇÃO (5-10min)
           ├─ Generate Excel reports
           ├─ Update Streamlit metadata
           ├─ Upload to Azure Blob (optional)
           └─ Log pipeline metrics

    Returns:
        dict: Complete pipeline execution summary with all sub-flow results
    """
    start_time = datetime.now()

    print("\n" + "="*70)
    print("  🚀 DAILY DATA PLATFORM PIPELINE - START")
    print("="*70)
    print(f"  Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

    # Track results from each stage
    results = {}
    pipeline_success = True

    # ─────────────────────────────────────────────────────────────────────
    # STAGE 1: INGESTÃO (Scraping)
    # ─────────────────────────────────────────────────────────────────────
    if run_scraping:
        print("\n" + "█"*70)
        print("  STAGE 1/4: INGESTÃO - Scraping Supermarkets")
        print("█"*70 + "\n")

        try:
            scraping_result = daily_scraper_flow(stores=scrape_stores)
            results['scraping'] = scraping_result

            if not scraping_result.get('success'):
                logger.warning("Scraping completed with some failures")
                # Continue pipeline even if some stores failed

        except Exception as e:
            logger.error(f"Scraping stage failed critically: {e}")
            results['scraping'] = {'success': False, 'error': str(e)}
            pipeline_success = False
            # Stop pipeline if scraping fails completely
            return _build_summary(results, start_time, pipeline_success)
    else:
        print("\n[SKIP] Scraping stage disabled")
        results['scraping'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────
    # STAGE 2: ENRIQUECIMENTO (OpenFoodFacts Delta-Sync)
    # ─────────────────────────────────────────────────────────────────────
    if run_enrichment:
        print("\n" + "█"*70)
        print("  STAGE 2/4: ENRIQUECIMENTO - OpenFoodFacts Delta-Sync")
        print("█"*70 + "\n")

        try:
            enrichment_result = daily_delta_sync_flow()
            results['enrichment'] = enrichment_result

            if not enrichment_result.get('success'):
                logger.warning("Enrichment completed with issues")
                # Continue pipeline

        except Exception as e:
            logger.error(f"Enrichment stage failed: {e}")
            results['enrichment'] = {'success': False, 'error': str(e)}
            # Continue pipeline even if enrichment fails
    else:
        print("\n[SKIP] Enrichment stage disabled")
        results['enrichment'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────
    # STAGE 3: TRANSFORMAÇÃO (DBT Models)
    # ─────────────────────────────────────────────────────────────────────
    if run_transform:
        print("\n" + "█"*70)
        print("  STAGE 3/4: TRANSFORMAÇÃO - DBT Models")
        print("█"*70 + "\n")

        try:
            transform_result = daily_transform_flow(
                run_tests=True,
                generate_docs=False  # Skip docs for daily runs (saves time)
            )
            results['transform'] = transform_result

            if not transform_result.get('success'):
                logger.error("Transformation stage failed")
                pipeline_success = False
                # Continue to analytics even if transform fails (some data might be available)

        except Exception as e:
            logger.error(f"Transformation stage failed critically: {e}")
            results['transform'] = {'success': False, 'error': str(e)}
            pipeline_success = False
            # Continue to analytics
    else:
        print("\n[SKIP] Transformation stage disabled")
        results['transform'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────
    # STAGE 4: DISPONIBILIZAÇÃO (Analytics & Reporting)
    # ─────────────────────────────────────────────────────────────────────
    if run_analytics:
        print("\n" + "█"*70)
        print("  STAGE 4/4: DISPONIBILIZAÇÃO - Analytics & Reports")
        print("█"*70 + "\n")

        try:
            analytics_result = daily_analytics_flow(
                generate_report=True,
                upload_azure=False,  # Enable when Azure is configured
                azure_layer="gold"
            )
            results['analytics'] = analytics_result

            # Analytics is optional - don't fail pipeline if it fails

        except Exception as e:
            logger.warning(f"Analytics stage failed (non-critical): {e}")
            results['analytics'] = {'success': False, 'error': str(e)}
            # Don't mark pipeline as failed
    else:
        print("\n[SKIP] Analytics stage disabled")
        results['analytics'] = {'skipped': True}

    # ─────────────────────────────────────────────────────────────────────
    # PIPELINE SUMMARY
    # ─────────────────────────────────────────────────────────────────────
    return _build_summary(results, start_time, pipeline_success)


def _build_summary(results: dict, start_time: datetime, success: bool) -> dict:
    """Build pipeline execution summary."""
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    summary = {
        'pipeline_start': start_time.isoformat(),
        'pipeline_end': end_time.isoformat(),
        'duration_seconds': duration,
        'duration_formatted': f"{int(duration // 60)}m {int(duration % 60)}s",
        'success': success,
        'stages': results
    }

    # Print summary
    print("\n" + "="*70)
    print("  📊 PIPELINE EXECUTION SUMMARY")
    print("="*70)
    print(f"  Start:    {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  End:      {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Duration: {summary['duration_formatted']}")
    print(f"  Status:   {'✅ SUCCESS' if success else '❌ FAILED'}")
    print("="*70)

    # Stage-by-stage summary
    for stage_name, stage_result in results.items():
        if isinstance(stage_result, dict):
            if stage_result.get('skipped'):
                print(f"  {stage_name.upper():15} ⊘ SKIPPED")
            elif stage_result.get('success', False):
                print(f"  {stage_name.upper():15} ✅ SUCCESS")
            else:
                print(f"  {stage_name.upper():15} ❌ FAILED")

    print("="*70)

    # Detailed metrics
    if 'scraping' in results and results['scraping'].get('total_products_scraped'):
        print(f"\n  📦 Products scraped: {results['scraping']['total_products_scraped']:,}")

    if 'enrichment' in results and results['enrichment'].get('delta_sync'):
        delta_stats = results['enrichment']['delta_sync']
        if delta_stats.get('products_updated'):
            print(f"  🌐 Products enriched: {delta_stats['products_updated']:,}")

    print("\n" + "="*70)
    print("  🏁 PIPELINE COMPLETE")
    print("="*70 + "\n")

    return summary


if __name__ == "__main__":
    # Run full pipeline locally (for testing)
    # For quick testing, you can disable stages:
    daily_pipeline_flow(
        run_scraping=False,    # Set to True to test scraping
        run_enrichment=True,
        run_transform=True,
        run_analytics=True,
    )
