"""
Prefect Flow - DBT Transformations (Bronze → Silver → Gold)

This flow orchestrates DBT model execution with data quality testing
and monitoring via Prefect dashboard.

Usage:
    # Run once (test)
    python src/orchestration/transform_flow.py

    # Deploy with schedule
    prefect deploy src/orchestration/transform_flow.py:daily_transform_flow \
        --name daily-transform \
        --cron "0 5 * * *"

    # Start worker (keep running)
    prefect worker start --pool market-scraper-pool
"""

from prefect import flow, task
from datetime import timedelta
import subprocess
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


@task(
    retries=2,
    retry_delay_seconds=300,  # 5 minutes
    log_prints=True,
    timeout_seconds=3600,  # 1 hour
)
def run_dbt_models(models: str = None) -> dict:
    """
    Run DBT models (transformations).

    Args:
        models: Optional DBT model selector (e.g., "staging.*", "gold.*")
                If None, runs all models

    Returns:
        dict: DBT execution statistics
    """
    print("[DBT RUN] Starting DBT transformations...")

    # Get DBT project path
    dbt_project_path = Path(__file__).parent.parent / "transform" / "dbt_project"

    # Build DBT command
    cmd = ["dbt", "run"]
    if models:
        cmd.extend(["--select", models])

    print(f"[DBT RUN] Command: {' '.join(cmd)}")
    print(f"[DBT RUN] Working directory: {dbt_project_path}")

    # Run DBT
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=dbt_project_path
    )

    if result.returncode != 0:
        error_msg = f"DBT run failed:\n{result.stderr}"
        logger.error(error_msg)
        raise Exception(f"DBT run failed with exit code {result.returncode}")

    # Parse output
    output = result.stdout
    print(f"[DBT RUN] Output:\n{output}")

    # Extract statistics
    stats = {
        'success': True,
        'models_selector': models or 'all',
        'output_lines': len(output.split('\n'))
    }

    # Try to extract "Completed successfully" count
    for line in output.split('\n'):
        if 'Completed successfully' in line:
            stats['completion_message'] = line.strip()

    print(f"[DBT RUN] ✅ Completed: {stats}")
    return stats


@task(
    retries=1,
    retry_delay_seconds=180,  # 3 minutes
    log_prints=True,
    timeout_seconds=1800,  # 30 minutes
)
def run_dbt_tests() -> dict:
    """
    Run DBT tests (data quality validation).

    Returns:
        dict: DBT test results
    """
    print("[DBT TEST] Starting data quality tests...")

    # Get DBT project path
    dbt_project_path = Path(__file__).parent.parent / "transform" / "dbt_project"

    # Run DBT tests
    result = subprocess.run(
        ["dbt", "test"],
        capture_output=True,
        text=True,
        cwd=dbt_project_path
    )

    # Note: DBT test returns non-zero if tests fail, but we still want to capture results
    output = result.stdout
    print(f"[DBT TEST] Output:\n{output}")

    # Parse test results
    stats = {
        'tests_run': True,
        'exit_code': result.returncode,
        'all_passed': result.returncode == 0,
        'output_lines': len(output.split('\n'))
    }

    # Extract pass/fail counts
    for line in output.split('\n'):
        if 'PASS' in line or 'FAIL' in line or 'ERROR' in line:
            stats['test_summary'] = line.strip()

    if result.returncode != 0:
        print(f"[DBT TEST] ⚠️ Some tests failed (exit code: {result.returncode})")
        print(f"[DBT TEST] Check output above for details")
        # Don't raise exception - we want to continue pipeline even if tests fail
        # but log the failure for monitoring
        logger.warning(f"DBT tests failed: {stats}")
    else:
        print(f"[DBT TEST] ✅ All tests passed!")

    return stats


@task(
    retries=1,
    retry_delay_seconds=60,
    log_prints=True,
)
def generate_dbt_docs() -> dict:
    """
    Generate DBT documentation.

    Returns:
        dict: Doc generation results
    """
    print("[DBT DOCS] Generating documentation...")

    # Get DBT project path
    dbt_project_path = Path(__file__).parent.parent / "transform" / "dbt_project"

    # Generate docs
    result = subprocess.run(
        ["dbt", "docs", "generate"],
        capture_output=True,
        text=True,
        cwd=dbt_project_path
    )

    if result.returncode != 0:
        logger.warning(f"DBT docs generation failed: {result.stderr}")
        return {'success': False, 'error': result.stderr}

    print("[DBT DOCS] ✅ Documentation generated")
    return {'success': True, 'docs_path': str(dbt_project_path / "target")}


@flow(
    name="daily-transform",
    description="Daily DBT transformations (bronze → silver → gold) with data quality testing",
    log_prints=True
)
def daily_transform_flow(run_tests: bool = True, generate_docs: bool = False) -> dict:
    """
    Main flow for DBT transformations.

    Args:
        run_tests: Whether to run data quality tests (default: True)
        generate_docs: Whether to generate DBT docs (default: False, saves time)

    Steps:
    1. Run staging models (bronze → staging)
    2. Run trusted models (staging → trusted)
    3. Run marts models (trusted → gold)
    4. Run data quality tests (optional)
    5. Generate documentation (optional)

    Returns:
        dict: Flow execution summary
    """
    print("="*60)
    print("  Daily Transform Flow - DBT Transformations")
    print("="*60)

    # Step 1: Run staging models (bronze → staging)
    print("\n[1/3] Running staging models...")
    staging_stats = run_dbt_models(models="staging")

    # Step 2: Run trusted models (staging → trusted)
    print("\n[2/3] Running trusted models...")
    trusted_stats = run_dbt_models(models="trusted")

    # Step 3: Run marts models (trusted → gold/marts)
    print("\n[3/3] Running marts models...")
    marts_stats = run_dbt_models(models="marts")

    # Step 4: Run tests (optional)
    test_stats = None
    if run_tests:
        print("\n[4/4] Running data quality tests...")
        test_stats = run_dbt_tests()

    # Step 5: Generate docs (optional)
    docs_stats = None
    if generate_docs:
        print("\n[DOCS] Generating documentation...")
        docs_stats = generate_dbt_docs()

    # Summary
    summary = {
        'staging': staging_stats,
        'trusted': trusted_stats,
        'marts': marts_stats,
        'tests': test_stats,
        'docs': docs_stats,
        'success': all([
            staging_stats.get('success'),
            trusted_stats.get('success'),
            marts_stats.get('success'),
        ])
    }

    print("\n" + "="*60)
    print("  Transform Flow Completed!")
    print("="*60)
    print(f"✅ Staging: {staging_stats.get('completion_message', 'OK')}")
    print(f"✅ Trusted: {trusted_stats.get('completion_message', 'OK')}")
    print(f"✅ Marts: {marts_stats.get('completion_message', 'OK')}")
    if test_stats:
        test_status = "✅ PASSED" if test_stats.get('all_passed') else "⚠️ FAILED"
        print(f"{test_status} Tests: {test_stats.get('test_summary', 'See logs')}")
    print("="*60 + "\n")

    return summary


if __name__ == "__main__":
    # Run flow locally (for testing)
    daily_transform_flow(run_tests=True, generate_docs=False)
