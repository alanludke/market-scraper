"""
Prefect Flow - Daily Delta Sync for OpenFoodFacts EAN Enrichment

This flow orchestrates the delta-sync process with automatic retries,
logging, and monitoring via Prefect dashboard.

Usage:
    # Run once (test)
    python src/orchestration/delta_sync_flow.py

    # Deploy with schedule
    prefect deploy src/orchestration/delta_sync_flow.py:daily_delta_sync_flow \
        --name daily-delta-sync \
        --cron "0 9 * * *"

    # Start worker (keep running)
    prefect worker start --pool default
"""

from prefect import flow, task
from prefect.tasks import task_input_hash
from datetime import timedelta
import subprocess
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


@task(
    retries=3,
    retry_delay_seconds=300,  # 5 minutes
    cache_key_fn=task_input_hash,
    cache_expiration=timedelta(hours=1),
    log_prints=True
)
def run_delta_sync():
    """
    Run OpenFoodFacts delta sync.

    Returns:
        dict: Execution statistics (products updated, deltas processed, etc.)
    """
    print("[1/2] Starting delta-sync...")

    # Get project root and add to PYTHONPATH
    project_root = Path(__file__).parent.parent.parent

    # Prepare environment with PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)

    # Run CLI command
    result = subprocess.run(
        ["python", "scripts/cli_enrich.py", "delta-sync"],
        capture_output=True,
        text=True,
        cwd=project_root,
        env=env
    )

    if result.returncode != 0:
        logger.error(f"Delta sync failed:\n{result.stderr}")
        raise Exception(f"Delta sync failed with exit code {result.returncode}")

    # Parse output for stats (optional)
    output = result.stdout
    print(f"Delta sync output:\n{output}")

    # Extract statistics (simple parsing)
    stats = {
        'success': True,
        'output_lines': len(output.split('\n'))
    }

    # Try to extract "Products updated: X"
    for line in output.split('\n'):
        if 'Products updated:' in line:
            try:
                products_updated = int(line.split(':')[1].strip())
                stats['products_updated'] = products_updated
            except:
                pass

    return stats


@task(
    retries=2,
    retry_delay_seconds=60,
    log_prints=True
)
def update_dbt_models():
    """
    Update DBT models after delta sync.

    Updates:
    - stg_openfoodfacts__products (staging layer)
    - dim_ean (conformed dimension)
    """
    print("[2/2] Updating DBT models...")

    result = subprocess.run(
        [
            "dbt", "run",
            "--select", "stg_openfoodfacts__products", "dim_ean"
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent / "transform" / "dbt_project"
    )

    if result.returncode != 0:
        logger.error(f"DBT update failed:\n{result.stderr}")
        raise Exception(f"DBT update failed with exit code {result.returncode}")

    # Parse DBT output
    output = result.stdout
    print(f"DBT output:\n{output}")

    return {'success': True, 'output_lines': len(output.split('\n'))}


@flow(
    name="daily-delta-sync",
    description="Daily OpenFoodFacts delta sync with DBT updates",
    log_prints=True
)
def daily_delta_sync_flow():
    """
    Main flow for daily delta sync.

    Steps:
    1. Run delta-sync (fetch and process new deltas)
    2. Update DBT models (refresh dim_ean)

    Returns:
        dict: Flow execution summary
    """
    print("="*60)
    print("  Daily Delta Sync Flow - OpenFoodFacts EAN Enrichment")
    print("="*60)

    # Step 1: Delta sync
    sync_stats = run_delta_sync()
    print(f"\n✅ Delta sync completed: {sync_stats}")

    # Step 2: Update DBT (only if products were updated)
    if sync_stats.get('products_updated', 0) > 0:
        print("\nProducts were updated, refreshing DBT models...")
        dbt_stats = update_dbt_models()
        print(f"✅ DBT models updated: {dbt_stats}")
    else:
        print("\nNo products updated, skipping DBT refresh")
        dbt_stats = {'skipped': True}

    # Summary
    summary = {
        'delta_sync': sync_stats,
        'dbt_update': dbt_stats,
        'success': True
    }

    print("\n" + "="*60)
    print("  Flow Completed Successfully!")
    print("="*60)
    print(f"Summary: {summary}")

    return summary


if __name__ == "__main__":
    # Run flow locally (for testing)
    daily_delta_sync_flow()
