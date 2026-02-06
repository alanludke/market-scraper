"""
Check old scraper progress (before Phase 1 metrics enhancement).
"""

import duckdb
import time

def analyze_old_scraper():
    db_path = "data/metrics/runs.duckdb"

    for attempt in range(5):
        try:
            conn = duckdb.connect(db_path, read_only=True)

            print("=" * 80)
            print("🔍 OLD SCRAPER PROGRESS (Before Phase 1 enhancements)")
            print("=" * 80)

            # Check which columns exist
            schema = conn.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'scraper_runs'
            """).fetchdf()

            print("\n📋 Available columns:", schema['column_name'].tolist())

            # Running runs (basic info only)
            print("\n📊 RUNNING RUNS")
            print("-" * 80)
            runs = conn.execute("""
                SELECT
                    run_id,
                    store,
                    status,
                    started_at,
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
                    if run['products_discovered']:
                        print(f"  Products discovered: {run['products_discovered']}")
            else:
                print("No running scraper found!")

            # Check if batches table exists
            try:
                batches_exist = conn.execute("""
                    SELECT COUNT(*) FROM scraper_batches LIMIT 1
                """).fetchone()[0]

                print("\n📦 BATCH PROGRESS (Last 20)")
                print("-" * 80)
                batches = conn.execute("""
                    SELECT
                        b.run_id,
                        r.store,
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
                        print(f"{status} {batch['store']:8} batch {batch['batch_number']:4} | "
                              f"{batch['products_count']:3} products | "
                              f"{batch['response_time_ms']:7.0f}ms | {batch['started_at']}")

                    # Summary
                    print("\n⚡ PERFORMANCE")
                    print("-" * 80)
                    avg_time = batches['response_time_ms'].mean()
                    max_time = batches['response_time_ms'].max()
                    total_batches = len(batches)
                    print(f"Batches analyzed: {total_batches}")
                    print(f"Avg batch time: {avg_time:.0f}ms ({avg_time/1000:.1f}s)")
                    print(f"Max batch time: {max_time:.0f}ms ({max_time/1000:.1f}s)")

            except:
                print("\n⚠️  No batch data available")

            conn.close()
            break

        except Exception as e:
            if "being used by another process" in str(e) or "locked" in str(e):
                print(f"DB locked, retrying... (attempt {attempt+1}/5)")
                time.sleep(2)
            else:
                print(f"Error: {e}")
                break
    else:
        print("❌ Could not access database")

    print("\n" + "=" * 80)
    print("⚠️  NOTE: This scraper is using OLD CODE (before Phase 1)")
    print("   To get performance metrics, cancel and restart with new code!")
    print("=" * 80)

if __name__ == "__main__":
    analyze_old_scraper()
