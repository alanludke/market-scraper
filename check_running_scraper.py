"""
Check scraper progress while it's running.

Shows what's happening in real-time by reading metrics with retry logic.
"""

import duckdb
import time
from datetime import datetime

def analyze_running_scraper():
    db_path = "data/metrics/runs.duckdb"

    # Try to connect with retries (DB might be locked)
    for attempt in range(5):
        try:
            conn = duckdb.connect(db_path, read_only=True)

            print("=" * 80)
            print("🔍 SCRAPER PROGRESS ANALYSIS (Real-time)")
            print("=" * 80)

            # 1. Running runs
            print("\n📊 RUNNING RUNS")
            print("-" * 80)
            runs = conn.execute("""
                SELECT
                    run_id,
                    store,
                    started_at,
                    discovery_mode,
                    discovery_duration_seconds,
                    products_discovered,
                    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)) / 60 as minutes_running
                FROM scraper_runs
                WHERE status = 'running'
                ORDER BY started_at
            """).fetchdf()

            if not runs.empty:
                for _, run in runs.iterrows():
                    print(f"\nStore: {run['store']}")
                    print(f"  Run ID: {run['run_id']}")
                    print(f"  Started: {run['started_at']}")
                    print(f"  Running for: {run['minutes_running']:.1f} minutes")
                    print(f"  Discovery mode: {run['discovery_mode']}")
                    if run['discovery_duration_seconds']:
                        print(f"  Discovery took: {run['discovery_duration_seconds']:.1f} seconds")
                    if run['products_discovered']:
                        print(f"  Products discovered: {run['products_discovered']}")
            else:
                print("No running scraper found!")

            # 2. Batch progress
            print("\n\n📦 BATCH PROGRESS (Last 20 batches)")
            print("-" * 80)
            batches = conn.execute("""
                SELECT
                    b.run_id,
                    r.store,
                    b.region,
                    b.batch_number,
                    b.products_count,
                    b.response_time_ms,
                    b.success,
                    b.started_at
                FROM scraper_batches b
                JOIN scraper_runs r ON b.run_id = r.run_id
                WHERE r.status = 'running'
                ORDER BY b.started_at DESC
                LIMIT 20
            """).fetchdf()

            if not batches.empty:
                for _, batch in batches.iterrows():
                    status = "✅" if batch['success'] else "❌"
                    print(f"{status} {batch['store']:8} {batch['region']:25} "
                          f"batch {batch['batch_number']:4} | "
                          f"{batch['products_count']:3} products | "
                          f"{batch['response_time_ms']:7.0f}ms | "
                          f"{batch['started_at']}")
            else:
                print("No batches found yet!")

            # 3. Performance summary
            print("\n\n⚡ PERFORMANCE SUMMARY (Running batches)")
            print("-" * 80)
            perf = conn.execute("""
                SELECT
                    r.store,
                    b.region,
                    COUNT(*) as total_batches,
                    AVG(b.response_time_ms) as avg_response_ms,
                    MAX(b.response_time_ms) as max_response_ms,
                    SUM(b.products_count) as total_products
                FROM scraper_batches b
                JOIN scraper_runs r ON b.run_id = r.run_id
                WHERE r.status = 'running'
                GROUP BY r.store, b.region
                ORDER BY avg_response_ms DESC
            """).fetchdf()

            if not perf.empty:
                print(f"{'Store':<10} {'Region':<25} {'Batches':>8} {'Avg ms':>10} {'Max ms':>10} {'Products':>10}")
                print("-" * 80)
                for _, row in perf.iterrows():
                    print(f"{row['store']:<10} {row['region']:<25} {row['total_batches']:>8} "
                          f"{row['avg_response_ms']:>10.0f} {row['max_response_ms']:>10.0f} {row['total_products']:>10}")

            # 4. Time estimate
            print("\n\n⏱️  TIME ESTIMATE")
            print("-" * 80)
            estimate = conn.execute("""
                SELECT
                    COUNT(DISTINCT b.run_id) as active_runs,
                    AVG(b.response_time_ms) as avg_batch_time_ms,
                    COUNT(*) as batches_completed
                FROM scraper_batches b
                JOIN scraper_runs r ON b.run_id = r.run_id
                WHERE r.status = 'running'
            """).fetchone()

            if estimate and estimate[2] > 0:
                avg_batch_ms = estimate[1]
                batches_done = estimate[2]

                print(f"Batches completed so far: {batches_done}")
                print(f"Average batch time: {avg_batch_ms:.0f}ms ({avg_batch_ms/1000:.1f}s)")

                # Rough estimate assuming ~200 batches per store (10k products / 50 batch_size)
                # Times 3 stores = 600 batches total
                estimated_total_batches = 600  # rough estimate
                estimated_remaining = estimated_total_batches - batches_done

                if estimated_remaining > 0:
                    estimated_time_remaining = (estimated_remaining * avg_batch_ms) / 1000 / 60
                    print(f"\n⚠️  Rough estimate: {estimated_remaining} batches remaining")
                    print(f"   Estimated time remaining: {estimated_time_remaining:.0f} minutes")

            conn.close()
            break

        except Exception as e:
            if "being used by another process" in str(e) or "locked" in str(e):
                print(f"DB locked, retrying in 2 seconds... (attempt {attempt+1}/5)")
                time.sleep(2)
            else:
                raise
    else:
        print("❌ Could not access database after 5 attempts")
        print("   The scraper is probably writing heavily to the DB")
        print("   Try canceling the scraper first, then run analysis")

if __name__ == "__main__":
    analyze_running_scraper()
