"""
Phase 1 verification tests: Logging + Metrics infrastructure.

Tests validate that:
1. MetricsCollector schema includes discovery-phase tracking columns
2. MetricsCollector can track discovery phase separately
3. Batch tracking includes region parameter
4. VTEXScraper integrates with metrics properly
5. Legacy scrapers show deprecation warnings

Run with: pytest tests/test_phase1_logging_metrics.py -v
"""

import pytest
import duckdb
import tempfile
import warnings
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.observability.metrics import MetricsCollector, get_metrics_collector


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_db():
    """Create a temporary DuckDB for testing."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def metrics_collector(temp_db):
    """Create a fresh MetricsCollector instance for each test."""
    return MetricsCollector(db_path=temp_db)


# ─────────────────────────────────────────────────────────────────────
# Schema Tests
# ─────────────────────────────────────────────────────────────────────

def test_schema_includes_discovery_columns(temp_db):
    """Verify scraper_runs table has discovery-phase tracking columns."""
    collector = MetricsCollector(db_path=temp_db)

    with duckdb.connect(temp_db) as conn:
        # Query schema
        schema = conn.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'scraper_runs'
        """).fetchdf()

        column_names = schema['column_name'].tolist()

        # Check for Phase 1 enhancement columns
        assert 'discovery_started_at' in column_names, \
            "Missing discovery_started_at column"
        assert 'discovery_finished_at' in column_names, \
            "Missing discovery_finished_at column"
        assert 'discovery_duration_seconds' in column_names, \
            "Missing discovery_duration_seconds column"
        assert 'discovery_mode' in column_names, \
            "Missing discovery_mode column"


def test_schema_includes_region_in_batches(temp_db):
    """Verify scraper_batches table has region column."""
    collector = MetricsCollector(db_path=temp_db)

    with duckdb.connect(temp_db) as conn:
        schema = conn.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'scraper_batches'
        """).fetchdf()

        column_names = schema['column_name'].tolist()

        # Check for Phase 1 enhancement column
        assert 'region' in column_names, \
            "Missing region column in scraper_batches"


# ─────────────────────────────────────────────────────────────────────
# Discovery Tracking Tests
# ─────────────────────────────────────────────────────────────────────

def test_start_discovery_updates_db(metrics_collector, temp_db):
    """Test that start_discovery() updates the database correctly."""
    # Start a run first
    run_id = "test_run_20260205_120000"
    metrics_collector.start_run(run_id, "bistek", region="florianopolis")

    # Start discovery
    metrics_collector.start_discovery(discovery_mode="sitemap")

    # Verify database update
    with duckdb.connect(temp_db) as conn:
        result = conn.execute("""
            SELECT discovery_started_at, discovery_mode
            FROM scraper_runs
            WHERE run_id = ?
        """, [run_id]).fetchone()

        assert result is not None, "Run not found in database"
        assert result[0] is not None, "discovery_started_at should be set"
        assert result[1] == "sitemap", "discovery_mode should be 'sitemap'"


def test_finish_discovery_calculates_duration(metrics_collector, temp_db):
    """Test that finish_discovery() calculates duration correctly."""
    import time

    run_id = "test_run_20260205_120001"
    metrics_collector.start_run(run_id, "fort", region="balneario_camboriu")
    metrics_collector.start_discovery(discovery_mode="category_tree")

    # Simulate discovery time
    time.sleep(0.1)

    metrics_collector.finish_discovery(products_discovered=1234)

    # Verify database update
    with duckdb.connect(temp_db) as conn:
        result = conn.execute("""
            SELECT
                discovery_finished_at,
                discovery_duration_seconds,
                products_discovered,
                discovery_mode
            FROM scraper_runs
            WHERE run_id = ?
        """, [run_id]).fetchone()

        assert result is not None, "Run not found"
        assert result[0] is not None, "discovery_finished_at should be set"
        assert result[1] is not None, "discovery_duration_seconds should be set"
        assert result[1] >= 0.1, "duration should be at least 0.1 seconds"
        assert result[2] == 1234, "products_discovered should be 1234"
        assert result[3] == "category_tree", "discovery_mode should be preserved"


def test_discovery_tracking_requires_active_run(metrics_collector):
    """Test that discovery tracking fails without an active run."""
    with pytest.raises(ValueError, match="No active run"):
        metrics_collector.start_discovery("sitemap")

    with pytest.raises(ValueError, match="No active run"):
        metrics_collector.finish_discovery(100)


# ─────────────────────────────────────────────────────────────────────
# Batch Tracking with Region Tests
# ─────────────────────────────────────────────────────────────────────

def test_record_batch_with_region(metrics_collector, temp_db):
    """Test that record_batch() stores region correctly."""
    run_id = "test_run_20260205_120002"
    metrics_collector.start_run(run_id, "giassi", region="florianopolis_santa_monica")

    # Record batch with explicit region
    metrics_collector.record_batch(
        batch_number=1,
        products_count=50,
        region="florianopolis_santa_monica",
        api_status_code=200,
        response_time_ms=234.5,
        success=True
    )

    # Verify database
    with duckdb.connect(temp_db) as conn:
        result = conn.execute("""
            SELECT region, products_count, api_status_code, response_time_ms
            FROM scraper_batches
            WHERE run_id = ?
        """, [run_id]).fetchone()

        assert result is not None, "Batch not found"
        assert result[0] == "florianopolis_santa_monica", "Region should match"
        assert result[1] == 50, "products_count should be 50"
        assert result[2] == 200, "api_status_code should be 200"
        assert result[3] == 234.5, "response_time_ms should match"


def test_record_batch_uses_current_region_as_fallback(metrics_collector, temp_db):
    """Test that record_batch() uses current_region if region not provided."""
    run_id = "test_run_20260205_120003"
    metrics_collector.start_run(run_id, "bistek", region="criciuma_centro")

    # Record batch WITHOUT explicit region
    metrics_collector.record_batch(
        batch_number=1,
        products_count=47,
        api_status_code=200
    )

    # Verify it uses current_region
    with duckdb.connect(temp_db) as conn:
        result = conn.execute("""
            SELECT region
            FROM scraper_batches
            WHERE run_id = ?
        """, [run_id]).fetchone()

        assert result is not None, "Batch not found"
        assert result[0] == "criciuma_centro", \
            "Region should fallback to current_region"


def test_track_batch_context_manager_with_region(metrics_collector, temp_db):
    """Test that track_batch() context manager accepts and uses region."""
    run_id = "test_run_20260205_120004"
    metrics_collector.start_run(run_id, "fort", region="itajai_saojoao")

    # Use context manager with region
    with metrics_collector.track_batch(1, region="itajai_saojoao") as batch:
        batch.products_count = 30
        batch.api_status_code = 206

    # Verify database
    with duckdb.connect(temp_db) as conn:
        result = conn.execute("""
            SELECT region, products_count, api_status_code, success
            FROM scraper_batches
            WHERE run_id = ?
        """, [run_id]).fetchone()

        assert result is not None, "Batch not found"
        assert result[0] == "itajai_saojoao", "Region should match"
        assert result[1] == 30, "products_count should be 30"
        assert result[2] == 206, "api_status_code should be 206"
        assert result[3] is True, "success should be True"


# ─────────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────────

def test_full_run_with_discovery_tracking(metrics_collector, temp_db):
    """Test complete run workflow with discovery tracking."""
    import time

    run_id = "test_run_20260205_120005"

    # 1. Start run
    metrics_collector.start_run(run_id, "bistek", region="florianopolis_costeira")

    # 2. Discovery phase
    metrics_collector.start_discovery("sitemap")
    time.sleep(0.05)
    metrics_collector.finish_discovery(products_discovered=500)

    # 3. Scraping phase (batches)
    for i in range(3):
        with metrics_collector.track_batch(i, region="florianopolis_costeira") as batch:
            batch.products_count = 50
            batch.api_status_code = 200
            time.sleep(0.01)

    # 4. Finish run
    metrics_collector.finish_run(
        status="success",
        products_scraped=150
    )

    # Verify complete workflow
    with duckdb.connect(temp_db) as conn:
        # Check run
        run = conn.execute("""
            SELECT
                status,
                discovery_mode,
                discovery_duration_seconds,
                products_discovered,
                products_scraped,
                duration_seconds
            FROM scraper_runs
            WHERE run_id = ?
        """, [run_id]).fetchone()

        assert run is not None, "Run not found"
        assert run[0] == "success", "Status should be success"
        assert run[1] == "sitemap", "Discovery mode should match"
        assert run[2] >= 0.05, "Discovery duration should be >= 0.05s"
        assert run[3] == 500, "products_discovered should match"
        assert run[4] == 150, "products_scraped should match"
        assert run[5] is not None, "duration_seconds should be set"

        # Check batches
        batches = conn.execute("""
            SELECT COUNT(*), SUM(products_count)
            FROM scraper_batches
            WHERE run_id = ?
        """, [run_id]).fetchone()

        assert batches[0] == 3, "Should have 3 batches"
        assert batches[1] == 150, "Total products should be 150"


# ─────────────────────────────────────────────────────────────────────
# Deprecation Warning Tests
# ─────────────────────────────────────────────────────────────────────

def test_legacy_scrapers_show_deprecation_warning():
    """Test that importing legacy scrapers shows deprecation warning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Import legacy module
        import src.scrapers

        # Check that a deprecation warning was raised
        assert len(w) >= 1, "Should raise at least one warning"
        assert issubclass(w[0].category, DeprecationWarning), \
            "Should be a DeprecationWarning"
        assert "deprecated" in str(w[0].message).lower(), \
            "Warning message should mention deprecation"
        assert "src.ingest.scrapers" in str(w[0].message), \
            "Warning should point to new location"


def test_legacy_vtex_scraper_has_deprecation_notice():
    """Test that legacy VTEXScraper docstring mentions deprecation."""
    from src.scrapers.vtex import VTEXScraper

    docstring = VTEXScraper.__doc__
    assert "DEPRECATED" in docstring, \
        "VTEXScraper docstring should mention DEPRECATED"
    assert "src.ingest.scrapers" in docstring, \
        "Should point to new location"


def test_legacy_base_scraper_has_deprecation_notice():
    """Test that legacy BaseScraper docstring mentions deprecation."""
    from src.scrapers.base import BaseScraper

    docstring = BaseScraper.__doc__
    assert "DEPRECATED" in docstring, \
        "BaseScraper docstring should mention DEPRECATED"
    assert "src.ingest.scrapers" in docstring, \
        "Should point to new location"


# ─────────────────────────────────────────────────────────────────────
# Performance Analysis Tests
# ─────────────────────────────────────────────────────────────────────

def test_analytics_queries_run_without_error(temp_db):
    """Test that analytics queries execute successfully with sample data."""
    # Create sample data
    collector = MetricsCollector(db_path=temp_db)

    # Add sample runs with discovery
    for i in range(3):
        run_id = f"test_run_{i}"
        collector.start_run(run_id, "bistek", region="florianopolis")
        collector.start_discovery("sitemap")
        collector.finish_discovery(products_discovered=100 + i*10)

        # Add sample batches
        for b in range(2):
            collector.record_batch(
                batch_number=b,
                products_count=50,
                region="florianopolis",
                api_status_code=200,
                response_time_ms=100.0 + i*10,
                success=True
            )

        collector.finish_run(status="success", products_scraped=100)

    # Test that queries run
    from src.observability import analytics_queries

    # Temporarily override DB_PATH for testing
    original_db_path = analytics_queries.DB_PATH
    analytics_queries.DB_PATH = temp_db

    try:
        # These should not raise exceptions
        df1 = analytics_queries.get_discovery_performance(days=7)
        assert not df1.empty, "Should have discovery data"

        df2 = analytics_queries.get_batch_performance_by_region(days=7)
        assert not df2.empty, "Should have batch data"

        df3 = analytics_queries.get_run_performance_summary(days=7)
        assert not df3.empty, "Should have run data"

        # Test optimization recommendations
        recommendations = analytics_queries.get_optimization_recommendations(days=7)
        assert 'recommendations' in recommendations, "Should have recommendations key"

    finally:
        # Restore original DB_PATH
        analytics_queries.DB_PATH = original_db_path


# ─────────────────────────────────────────────────────────────────────
# Run all tests
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # CLI usage: python tests/test_phase1_logging_metrics.py
    pytest.main([__file__, "-v", "--tb=short"])
