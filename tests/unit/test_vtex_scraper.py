"""
Unit tests for VTEXScraper (Phase 3).

Tests validate:
1. Product validation with Pydantic schemas
2. Region cookie generation
3. Discovery modes (sitemap vs category_tree)
4. Batch processing logic
5. Error handling and logging

Run with: pytest tests/unit/test_vtex_scraper.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
from pydantic import ValidationError

from src.ingest.scrapers.vtex import VTEXScraper, RegionResolver


# ─────────────────────────────────────────────────────────────────────
# VTEXScraper Initialization Tests
# ─────────────────────────────────────────────────────────────────────

def test_vtex_scraper_initialization(sample_store_config):
    """Test that VTEXScraper initializes correctly."""
    scraper = VTEXScraper("bistek", sample_store_config)

    assert scraper.store_name == "bistek"
    assert scraper.base_url == "https://www.bistek.com.br"
    assert scraper.discovery == "sitemap"
    assert scraper.global_discovery is True
    assert scraper.cookie_domain == ".bistek.com.br"
    assert scraper.validation_errors_count == 0
    assert scraper.resolver is not None


def test_vtex_scraper_giassi_mode(sample_giassi_config):
    """Test Giassi-style configuration (global_discovery=false)."""
    scraper = VTEXScraper("giassi", sample_giassi_config)

    assert scraper.global_discovery is False
    assert scraper.discovery == "category_tree"


# ─────────────────────────────────────────────────────────────────────
# Product Validation Tests (Phase 2 Integration)
# ─────────────────────────────────────────────────────────────────────

def test_validate_products_with_valid_data(sample_store_config, mock_vtex_product):
    """Test that valid products pass validation."""
    scraper = VTEXScraper("bistek", sample_store_config)

    products = [mock_vtex_product]
    validated = scraper.validate_products(products)

    assert len(validated) == 1
    assert validated[0]["productId"] == "100"
    assert validated[0]["productName"] == "Arroz Integral Tio João 1kg"
    assert scraper.validation_errors_count == 0


def test_validate_products_filters_invalid_data(sample_store_config, mock_vtex_invalid_product):
    """Test that invalid products are filtered out."""
    scraper = VTEXScraper("bistek", sample_store_config)

    products = [mock_vtex_invalid_product]
    validated = scraper.validate_products(products)

    # Invalid product should be filtered out
    assert len(validated) == 0
    assert scraper.validation_errors_count == 1


def test_validate_products_mixed_valid_invalid(
    sample_store_config, mock_vtex_product, mock_vtex_invalid_product
):
    """Test validation with mix of valid and invalid products."""
    scraper = VTEXScraper("bistek", sample_store_config)

    products = [mock_vtex_product, mock_vtex_invalid_product, mock_vtex_product]
    validated = scraper.validate_products(products)

    # Should filter out 1 invalid, keep 2 valid
    assert len(validated) == 2
    assert scraper.validation_errors_count == 1


def test_validate_products_logs_errors(sample_store_config, mock_vtex_invalid_product):
    """Test that validation errors are logged."""
    scraper = VTEXScraper("bistek", sample_store_config)

    with patch("src.ingest.scrapers.vtex.logger") as mock_logger:
        products = [mock_vtex_invalid_product]
        validated = scraper.validate_products(products)

        # Should have logged a warning
        assert mock_logger.warning.called
        assert scraper.validation_errors_count == 1


def test_validate_products_handles_unexpected_errors(sample_store_config):
    """Test that unexpected validation errors are caught."""
    scraper = VTEXScraper("bistek", sample_store_config)

    # Malformed product that will cause unexpected error
    malformed_product = {"completely": "invalid"}

    with patch("src.ingest.scrapers.vtex.logger") as mock_logger:
        validated = scraper.validate_products([malformed_product])

        # Should log error and skip product
        assert len(validated) == 0
        assert scraper.validation_errors_count == 1
        assert mock_logger.error.called or mock_logger.warning.called


# ─────────────────────────────────────────────────────────────────────
# RegionResolver Tests
# ─────────────────────────────────────────────────────────────────────

def test_region_resolver_initialization(mock_requests_session):
    """Test RegionResolver initialization."""
    resolver = RegionResolver(mock_requests_session, "https://www.bistek.com.br")

    assert resolver.session == mock_requests_session
    assert resolver.base_url == "https://www.bistek.com.br"


def test_region_resolver_get_segment_cookie_with_manual_region(mock_requests_session):
    """Test segment cookie generation with manual region ID."""
    resolver = RegionResolver(mock_requests_session, "https://www.bistek.com.br")

    cookie = resolver.get_segment_cookie(
        postal_code="88095-000",
        sales_channel="1",
        manual_region_id="v2.5BE6A0CEC1DA8E9954E2"
    )

    # Should not call API if manual region provided
    assert not mock_requests_session.get.called
    assert cookie is not None
    assert isinstance(cookie, str)


def test_region_resolver_get_segment_cookie_api_call(mock_requests_session):
    """Test segment cookie generation via API."""
    # Mock API response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"id": "v2.5BE6A0CEC1DA8E9954E2"}]
    mock_requests_session.get.return_value = mock_response

    resolver = RegionResolver(mock_requests_session, "https://www.bistek.com.br")

    cookie = resolver.get_segment_cookie(postal_code="88095-000", sales_channel="1")

    # Should call API
    assert mock_requests_session.get.called
    call_args = mock_requests_session.get.call_args
    assert "88095000" in call_args[0][0]  # CEP without dash

    assert cookie is not None


def test_region_resolver_handles_api_failure(mock_requests_session):
    """Test that API failures are handled gracefully."""
    # Mock API error
    mock_requests_session.get.side_effect = Exception("API Error")

    resolver = RegionResolver(mock_requests_session, "https://www.bistek.com.br")

    # Should not raise, just log warning
    cookie = resolver.get_segment_cookie(postal_code="88095-000")

    # Cookie should still be generated (with regionId=None)
    assert cookie is not None


# ─────────────────────────────────────────────────────────────────────
# Discovery Tests
# ─────────────────────────────────────────────────────────────────────

@patch("src.ingest.scrapers.vtex.ET")
def test_discover_via_sitemap(mock_et, sample_store_config, mock_requests_session):
    """Test sitemap-based discovery."""
    # Mock sitemap XML response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b"""<?xml version="1.0"?>
    <urlset>
        <url><loc>https://www.bistek.com.br/product-1/p</loc></url>
        <url><loc>https://www.bistek.com.br/product-2/p</loc></url>
    </urlset>
    """
    mock_requests_session.get.return_value = mock_response

    # Mock XML parsing
    mock_root = Mock()
    mock_urls = [
        Mock(text="https://www.bistek.com.br/product-1/p"),
        Mock(text="https://www.bistek.com.br/product-2/p"),
    ]
    mock_root.findall.return_value = mock_urls
    mock_et.fromstring.return_value = mock_root

    scraper = VTEXScraper("bistek", sample_store_config)
    scraper.session = mock_requests_session

    product_ids = scraper._discover_via_sitemap(limit=None)

    # Should extract product IDs from URLs
    assert isinstance(product_ids, list)
    # Actual extraction logic would parse IDs from URLs


@patch("src.ingest.scrapers.vtex.VTEXScraper._get_department_ids")
def test_discover_via_categories(mock_get_depts, sample_store_config, mock_requests_session):
    """Test category-tree based discovery."""
    # Mock department IDs
    mock_get_depts.return_value = [1, 2, 3]

    # Mock API search response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"productId": "100"},
        {"productId": "101"},
        {"productId": "102"},
    ]
    mock_requests_session.get.return_value = mock_response

    scraper = VTEXScraper("bistek", sample_store_config)
    scraper.session = mock_requests_session

    product_ids = scraper._discover_via_categories(limit=10)

    # Should discover products from categories
    assert isinstance(product_ids, list)
    assert len(product_ids) <= 10  # Respects limit


# ─────────────────────────────────────────────────────────────────────
# Cookie Management Tests
# ─────────────────────────────────────────────────────────────────────

def test_set_region_cookie_success(sample_store_config, mock_requests_session):
    """Test region cookie is set correctly."""
    scraper = VTEXScraper("bistek", sample_store_config)
    scraper.session = mock_requests_session

    # Mock resolver
    scraper.resolver.get_segment_cookie = Mock(return_value="mock_cookie_value")

    success = scraper._set_region_cookie("florianopolis_costeira")

    assert success is True
    assert scraper.session.cookies.set.called
    call_args = scraper.session.cookies.set.call_args
    assert call_args[0][0] == "vtex_segment"
    assert call_args[0][1] == "mock_cookie_value"


def test_set_region_cookie_failure(sample_store_config, mock_requests_session):
    """Test handling of cookie generation failure."""
    scraper = VTEXScraper("bistek", sample_store_config)
    scraper.session = mock_requests_session

    # Mock resolver failure
    scraper.resolver.get_segment_cookie = Mock(return_value=None)

    success = scraper._set_region_cookie("florianopolis_costeira")

    assert success is False


# ─────────────────────────────────────────────────────────────────────
# Integration Tests (with mocked metrics)
# ─────────────────────────────────────────────────────────────────────

@patch("src.ingest.scrapers.vtex.get_metrics_collector")
def test_scrape_by_ids_with_validation(
    mock_get_metrics, sample_store_config, mock_requests_session, mock_vtex_product, temp_dir
):
    """Test _scrape_by_ids integrates with validation."""
    # Mock metrics collector
    mock_metrics = Mock()
    mock_metrics.track_batch = MagicMock()
    mock_get_metrics.return_value = mock_metrics

    # Mock API response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [mock_vtex_product]
    mock_requests_session.get.return_value = mock_response

    scraper = VTEXScraper("bistek", sample_store_config)
    scraper.session = mock_requests_session
    scraper.output_base = temp_dir

    # Mock resolver
    scraper.resolver.get_segment_cookie = Mock(return_value="mock_cookie")

    product_ids = ["100"]

    # Run scraping
    with patch.object(scraper, 'consolidate_batches'):
        with patch.object(scraper, 'validate_run'):
            scraper._scrape_by_ids("florianopolis_costeira", product_ids)

    # Validation should have been called
    assert scraper.validation_errors_count == 0


# ─────────────────────────────────────────────────────────────────────
# Error Handling Tests
# ─────────────────────────────────────────────────────────────────────

@patch("src.ingest.scrapers.vtex.get_metrics_collector")
def test_scrape_by_ids_handles_api_error(
    mock_get_metrics, sample_store_config, mock_requests_session, temp_dir
):
    """Test that API errors in batch are caught and logged."""
    # Mock metrics
    mock_metrics = Mock()
    mock_batch_context = Mock()
    mock_batch_context.__enter__ = Mock(return_value=mock_batch_context)
    mock_batch_context.__exit__ = Mock(return_value=False)
    mock_metrics.track_batch.return_value = mock_batch_context
    mock_get_metrics.return_value = mock_metrics

    # Mock API error
    mock_requests_session.get.side_effect = Exception("API Connection Error")

    scraper = VTEXScraper("bistek", sample_store_config)
    scraper.session = mock_requests_session
    scraper.output_base = temp_dir
    scraper.resolver.get_segment_cookie = Mock(return_value="mock_cookie")

    product_ids = ["100"]

    with patch("src.ingest.scrapers.vtex.logger") as mock_logger:
        with patch.object(scraper, 'consolidate_batches'):
            with patch.object(scraper, 'validate_run'):
                scraper._scrape_by_ids("florianopolis_costeira", product_ids)

    # Should have logged error
    assert mock_logger.error.called


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
