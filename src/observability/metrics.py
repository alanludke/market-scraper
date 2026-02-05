"""
Operational metrics collection using DuckDB.

Tracks run-level and batch-level metrics for observability.
"""

import duckdb
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from typing import Optional
import time


class MetricsCollector:
    """
    Singleton-like metrics collector that persists operational data to DuckDB.

    Tables:
    - scraper_runs: High-level run metadata
    - scraper_batches: Batch-level metrics for detailed analysis
    """

    def __init__(self, db_path: str = "data/metrics/runs.duckdb"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

        # Current run context
        self.current_run_id: Optional[str] = None
        self.current_store: Optional[str] = None
        self.current_region: Optional[str] = None
        self.run_start_time: Optional[float] = None

    def _init_schema(self):
        """Create tables if they don't exist."""
        with duckdb.connect(str(self.db_path)) as conn:
            # Runs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scraper_runs (
                    run_id VARCHAR PRIMARY KEY,
                    store VARCHAR NOT NULL,
                    region VARCHAR,
                    started_at TIMESTAMP NOT NULL,
                    finished_at TIMESTAMP,
                    status VARCHAR NOT NULL,  -- 'running', 'success', 'failed', 'partial'
                    products_discovered INTEGER,
                    products_scraped INTEGER,
                    bytes_downloaded BIGINT,
                    api_calls_count INTEGER,
                    api_errors_count INTEGER,
                    duration_seconds DOUBLE,
                    error_message TEXT,
                    output_path VARCHAR
                )
            """)

            # Batches table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scraper_batches (
                    batch_id VARCHAR PRIMARY KEY,
                    run_id VARCHAR NOT NULL,
                    batch_number INTEGER,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    products_count INTEGER,
                    api_status_code INTEGER,
                    response_time_ms DOUBLE,
                    retry_count INTEGER,
                    success BOOLEAN
                )
            """)

    def start_run(self, run_id: str, store: str, region: str = None):
        """Mark the start of a scraper run."""
        self.current_run_id = run_id
        self.current_store = store
        self.current_region = region
        self.run_start_time = time.time()

        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT INTO scraper_runs (
                    run_id, store, region, started_at, status
                ) VALUES (?, ?, ?, ?, 'running')
            """, [run_id, store, region, datetime.now()])

    def finish_run(
        self,
        status: str,
        products_discovered: int = None,
        products_scraped: int = None,
        output_path: str = None,
        error_message: str = None,
        **kwargs
    ):
        """Mark the end of a scraper run with final metrics."""
        if not self.current_run_id:
            raise ValueError("No active run. Call start_run() first.")

        duration = time.time() - self.run_start_time if self.run_start_time else None

        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute("""
                UPDATE scraper_runs
                SET finished_at = ?,
                    status = ?,
                    products_discovered = ?,
                    products_scraped = ?,
                    duration_seconds = ?,
                    output_path = ?,
                    error_message = ?
                WHERE run_id = ?
            """, [
                datetime.now(),
                status,
                products_discovered,
                products_scraped,
                duration,
                output_path,
                error_message,
                self.current_run_id
            ])

        # Reset context
        self.current_run_id = None
        self.current_store = None
        self.current_region = None
        self.run_start_time = None

    def record_batch(
        self,
        batch_number: int,
        products_count: int,
        api_status_code: int = None,
        response_time_ms: float = None,
        retry_count: int = 0,
        success: bool = True
    ):
        """Record batch-level metrics."""
        if not self.current_run_id:
            return  # Silently skip if no active run

        batch_id = f"{self.current_run_id}_batch_{batch_number}"

        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT INTO scraper_batches (
                    batch_id, run_id, batch_number,
                    started_at, finished_at,
                    products_count, api_status_code,
                    response_time_ms, retry_count, success
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                batch_id,
                self.current_run_id,
                batch_number,
                datetime.now(),
                datetime.now(),
                products_count,
                api_status_code,
                response_time_ms,
                retry_count,
                success
            ])

    @contextmanager
    def track_batch(self, batch_number: int):
        """
        Context manager for tracking batch execution.

        Usage:
            with metrics.track_batch(1) as batch:
                products = scrape_batch()
                batch.products_count = len(products)
                batch.api_status_code = 200
        """
        class BatchContext:
            def __init__(self, collector, batch_num):
                self.collector = collector
                self.batch_num = batch_num
                self.products_count = 0
                self.api_status_code = None
                self.response_time_ms = None
                self.retry_count = 0
                self.success = True
                self.start_time = time.time()

        batch = BatchContext(self, batch_number)

        try:
            yield batch
        except Exception:
            batch.success = False
            raise
        finally:
            elapsed_ms = (time.time() - batch.start_time) * 1000
            if batch.response_time_ms is None:
                batch.response_time_ms = elapsed_ms

            self.record_batch(
                batch_number=batch.batch_num,
                products_count=batch.products_count,
                api_status_code=batch.api_status_code,
                response_time_ms=batch.response_time_ms,
                retry_count=batch.retry_count,
                success=batch.success
            )

    def get_run_stats(self, days: int = 7):
        """Get run statistics for the last N days."""
        with duckdb.connect(str(self.db_path)) as conn:
            return conn.execute("""
                SELECT
                    store,
                    COUNT(*) as total_runs,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_runs,
                    AVG(duration_seconds) as avg_duration_seconds,
                    SUM(products_scraped) as total_products
                FROM scraper_runs
                WHERE started_at > CURRENT_TIMESTAMP - INTERVAL ? DAY
                GROUP BY store
            """, [days]).fetchdf()


# Global instance (can be imported directly)
_metrics_instance = None


def get_metrics_collector(db_path: str = "data/metrics/runs.duckdb") -> MetricsCollector:
    """Get or create the global metrics collector instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = MetricsCollector(db_path)
    return _metrics_instance
