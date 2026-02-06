"""
Analytics queries for operational metrics.

These queries help investigate scraper performance and identify bottlenecks.
All queries run against data/metrics/runs.duckdb.

Usage:
    from src.observability.analytics_queries import get_discovery_performance

    df = get_discovery_performance(days=7)
    print(df)
"""

import duckdb
from pathlib import Path
from typing import Optional
import pandas as pd


DB_PATH = "data/metrics/runs.duckdb"


def _get_conn():
    """Get DuckDB connection. Thread-safe (DuckDB handles locking)."""
    db_path = Path(DB_PATH)
    if not db_path.exists():
        raise FileNotFoundError(
            f"Metrics database not found at {db_path}. "
            "Run a scraper first to create the database."
        )
    return duckdb.connect(str(db_path), read_only=True)


# ─────────────────────────────────────────────────────────────────────
# Discovery Phase Performance
# ─────────────────────────────────────────────────────────────────────

def get_discovery_performance(days: int = 7) -> pd.DataFrame:
    """
    Analyze discovery phase performance across stores.

    Shows average discovery duration, products discovered, and discovery mode.
    Helps identify if discovery is the bottleneck.

    Returns:
        DataFrame with columns: store, discovery_mode, avg_duration_seconds,
        total_products, avg_products_per_second
    """
    with _get_conn() as conn:
        return conn.execute("""
            SELECT
                store,
                discovery_mode,
                COUNT(*) as total_runs,
                AVG(discovery_duration_seconds) as avg_discovery_duration,
                SUM(products_discovered) as total_products_discovered,
                AVG(products_discovered) as avg_products_per_run,
                AVG(products_discovered / NULLIF(discovery_duration_seconds, 0))
                    as avg_products_per_second
            FROM scraper_runs
            WHERE started_at > CURRENT_TIMESTAMP - INTERVAL ? DAY
              AND discovery_duration_seconds IS NOT NULL
            GROUP BY store, discovery_mode
            ORDER BY avg_discovery_duration DESC
        """, [days]).fetchdf()


def get_discovery_trend(store: str = None, days: int = 30) -> pd.DataFrame:
    """
    Get discovery duration trend over time.

    Shows if discovery is getting slower or faster over time.
    Useful for detecting API degradation or inventory growth.

    Args:
        store: Filter by specific store (None = all stores)
        days: Number of days to analyze

    Returns:
        DataFrame with columns: date, store, avg_discovery_duration,
        products_discovered
    """
    where_clause = ""
    params = [days]
    if store:
        where_clause = "AND store = ?"
        params.append(store)

    with _get_conn() as conn:
        return conn.execute(f"""
            SELECT
                DATE_TRUNC('day', started_at) as date,
                store,
                AVG(discovery_duration_seconds) as avg_discovery_duration,
                AVG(products_discovered) as avg_products_discovered,
                COUNT(*) as runs_count
            FROM scraper_runs
            WHERE started_at > CURRENT_TIMESTAMP - INTERVAL ? DAY
              AND discovery_duration_seconds IS NOT NULL
              {where_clause}
            GROUP BY DATE_TRUNC('day', started_at), store
            ORDER BY date DESC, store
        """, params).fetchdf()


# ─────────────────────────────────────────────────────────────────────
# Batch Performance by Region
# ─────────────────────────────────────────────────────────────────────

def get_batch_performance_by_region(days: int = 7) -> pd.DataFrame:
    """
    Analyze batch performance by region to identify slow regions.

    This is CRITICAL for identifying geographic bottlenecks!

    Returns:
        DataFrame with columns: region, total_batches, avg_response_time_ms,
        p50_response_time_ms, p95_response_time_ms, error_rate
    """
    with _get_conn() as conn:
        return conn.execute("""
            SELECT
                region,
                COUNT(*) as total_batches,
                AVG(response_time_ms) as avg_response_time_ms,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY response_time_ms)
                    as p50_response_time_ms,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms)
                    as p95_response_time_ms,
                AVG(products_count) as avg_products_per_batch,
                SUM(CASE WHEN NOT success THEN 1 ELSE 0 END)::FLOAT / COUNT(*)
                    as error_rate
            FROM scraper_batches
            JOIN scraper_runs ON scraper_batches.run_id = scraper_runs.run_id
            WHERE scraper_runs.started_at > CURRENT_TIMESTAMP - INTERVAL ? DAY
              AND region IS NOT NULL
            GROUP BY region
            ORDER BY p95_response_time_ms DESC
        """, [days]).fetchdf()


def get_slowest_batches(days: int = 7, limit: int = 20) -> pd.DataFrame:
    """
    Get the slowest batches to identify outliers.

    Helps pinpoint specific API calls that are taking too long.

    Args:
        days: Number of days to analyze
        limit: Max number of results

    Returns:
        DataFrame with slowest batches, including run context
    """
    with _get_conn() as conn:
        return conn.execute("""
            SELECT
                scraper_batches.run_id,
                scraper_runs.store,
                scraper_batches.region,
                scraper_batches.batch_number,
                scraper_batches.response_time_ms,
                scraper_batches.products_count,
                scraper_batches.api_status_code,
                scraper_batches.retry_count,
                scraper_batches.started_at
            FROM scraper_batches
            JOIN scraper_runs ON scraper_batches.run_id = scraper_runs.run_id
            WHERE scraper_runs.started_at > CURRENT_TIMESTAMP - INTERVAL ? DAY
              AND scraper_batches.response_time_ms IS NOT NULL
            ORDER BY scraper_batches.response_time_ms DESC
            LIMIT ?
        """, [days, limit]).fetchdf()


# ─────────────────────────────────────────────────────────────────────
# Overall Run Performance
# ─────────────────────────────────────────────────────────────────────

def get_run_performance_summary(days: int = 7) -> pd.DataFrame:
    """
    Overall run performance summary by store.

    Shows end-to-end run duration, success rate, and throughput.

    Returns:
        DataFrame with columns: store, total_runs, success_rate,
        avg_duration_seconds, avg_products_scraped
    """
    with _get_conn() as conn:
        return conn.execute("""
            SELECT
                store,
                COUNT(*) as total_runs,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END)::FLOAT / COUNT(*)
                    as success_rate,
                AVG(duration_seconds) as avg_total_duration,
                AVG(discovery_duration_seconds) as avg_discovery_duration,
                AVG(duration_seconds - COALESCE(discovery_duration_seconds, 0))
                    as avg_scraping_duration,
                AVG(products_scraped) as avg_products_scraped,
                AVG(products_scraped / NULLIF(duration_seconds, 0))
                    as avg_products_per_second_overall
            FROM scraper_runs
            WHERE started_at > CURRENT_TIMESTAMP - INTERVAL ? DAY
              AND status IN ('success', 'failed')
            GROUP BY store
            ORDER BY avg_total_duration DESC
        """, [days]).fetchdf()


def get_performance_breakdown(run_id: str) -> dict:
    """
    Detailed performance breakdown for a specific run.

    Shows discovery vs scraping time, batch statistics, etc.
    Useful for deep-dive investigation.

    Args:
        run_id: The run ID to analyze

    Returns:
        Dictionary with run metadata and performance stats
    """
    with _get_conn() as conn:
        # Run-level stats
        run_stats = conn.execute("""
            SELECT
                run_id,
                store,
                region,
                started_at,
                finished_at,
                status,
                discovery_mode,
                discovery_duration_seconds,
                duration_seconds,
                products_discovered,
                products_scraped
            FROM scraper_runs
            WHERE run_id = ?
        """, [run_id]).fetchdf()

        if run_stats.empty:
            raise ValueError(f"Run {run_id} not found")

        # Batch-level stats
        batch_stats = conn.execute("""
            SELECT
                COUNT(*) as total_batches,
                AVG(response_time_ms) as avg_response_time_ms,
                MIN(response_time_ms) as min_response_time_ms,
                MAX(response_time_ms) as max_response_time_ms,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms)
                    as p95_response_time_ms,
                SUM(products_count) as total_products,
                SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failed_batches
            FROM scraper_batches
            WHERE run_id = ?
        """, [run_id]).fetchdf()

        return {
            "run": run_stats.to_dict('records')[0],
            "batches": batch_stats.to_dict('records')[0] if not batch_stats.empty else {}
        }


# ─────────────────────────────────────────────────────────────────────
# Performance Optimization Recommendations
# ─────────────────────────────────────────────────────────────────────

def get_optimization_recommendations(days: int = 7) -> dict:
    """
    Automated analysis to identify performance bottlenecks.

    Returns:
        Dictionary with recommendations and supporting data
    """
    recommendations = []

    # Check if discovery is the bottleneck
    discovery_perf = get_discovery_performance(days)
    if not discovery_perf.empty:
        for _, row in discovery_perf.iterrows():
            discovery_pct = (row['avg_discovery_duration'] /
                           (row['avg_discovery_duration'] + 100)) * 100  # rough estimate
            if discovery_pct > 30:
                recommendations.append({
                    "type": "discovery_slow",
                    "store": row['store'],
                    "discovery_mode": row['discovery_mode'],
                    "avg_duration": row['avg_discovery_duration'],
                    "recommendation": f"Discovery takes {discovery_pct:.0f}% of total time. "
                                    f"Consider optimizing {row['discovery_mode']} logic or "
                                    f"caching product IDs."
                })

    # Check for slow regions
    region_perf = get_batch_performance_by_region(days)
    if not region_perf.empty:
        median_p95 = region_perf['p95_response_time_ms'].median()
        slow_regions = region_perf[region_perf['p95_response_time_ms'] > median_p95 * 2]

        for _, row in slow_regions.iterrows():
            recommendations.append({
                "type": "slow_region",
                "region": row['region'],
                "p95_ms": row['p95_response_time_ms'],
                "error_rate": row['error_rate'],
                "recommendation": f"Region '{row['region']}' has 2x slower API response times "
                                f"({row['p95_response_time_ms']:.0f}ms p95). "
                                f"Consider increasing request_delay or investigating VTEX API health."
            })

    # Check for high error rates
    run_perf = get_run_performance_summary(days)
    if not run_perf.empty:
        for _, row in run_perf.iterrows():
            if row['success_rate'] < 0.95:
                recommendations.append({
                    "type": "high_error_rate",
                    "store": row['store'],
                    "success_rate": row['success_rate'],
                    "recommendation": f"Store '{row['store']}' has {(1-row['success_rate'])*100:.1f}% "
                                    f"failure rate. Check error logs for root cause."
                })

    return {
        "recommendations": recommendations,
        "discovery_performance": discovery_perf.to_dict('records'),
        "region_performance": region_perf.to_dict('records'),
        "run_performance": run_perf.to_dict('records')
    }


# ─────────────────────────────────────────────────────────────────────
# Convenience CLI
# ─────────────────────────────────────────────────────────────────────

def print_performance_report(days: int = 7):
    """
    Print a comprehensive performance report to console.

    Useful for quick investigation without opening a notebook.
    """
    print("=" * 80)
    print(f"SCRAPER PERFORMANCE REPORT (Last {days} Days)")
    print("=" * 80)

    print("\n📊 OVERALL RUN PERFORMANCE")
    print("-" * 80)
    run_perf = get_run_performance_summary(days)
    if not run_perf.empty:
        print(run_perf.to_string(index=False))
    else:
        print("No data available")

    print("\n🔍 DISCOVERY PHASE PERFORMANCE")
    print("-" * 80)
    discovery_perf = get_discovery_performance(days)
    if not discovery_perf.empty:
        print(discovery_perf.to_string(index=False))
    else:
        print("No data available")

    print("\n🌎 BATCH PERFORMANCE BY REGION")
    print("-" * 80)
    region_perf = get_batch_performance_by_region(days)
    if not region_perf.empty:
        print(region_perf.head(10).to_string(index=False))
    else:
        print("No data available")

    print("\n💡 OPTIMIZATION RECOMMENDATIONS")
    print("-" * 80)
    recommendations = get_optimization_recommendations(days)
    if recommendations['recommendations']:
        for i, rec in enumerate(recommendations['recommendations'], 1):
            print(f"{i}. [{rec['type'].upper()}] {rec['recommendation']}")
    else:
        print("No performance issues detected. Great job! 🎉")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    # CLI usage: python src/observability/analytics_queries.py
    import sys

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    print_performance_report(days)
