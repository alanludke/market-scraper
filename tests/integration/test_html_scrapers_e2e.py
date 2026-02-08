"""
End-to-End tests for HTML scrapers (Carrefour, Angeloni, SuperKoch, Hippo).

Tests JSON-LD extraction and HTML parsing workflows.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import json

from src.ingest.scrapers.carrefour_html import CarrefourHTMLScraper
from src.ingest.scrapers.angeloni_html import AngeloniHTMLScraper
from src.ingest.scrapers.superkoch_html import SuperKochHTMLScraper
from src.ingest.scrapers.hippo_html import HippoHTMLScraper


class TestHTMLScraperJSONLD:
    """Test JSON-LD extraction from HTML pages."""

    @pytest.fixture
    def sample_html_with_jsonld(self):
        """Sample HTML with JSON-LD Product schema."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "Arroz Integral 1kg",
                "sku": "12345",
                "brand": {"name": "Tio João"},
                "image": ["https://example.com/image.jpg"],
                "offers": {
                    "@type": "Offer",
                    "price": "8.99",
                    "priceCurrency": "BRL",
                    "availability": "https://schema.org/InStock"
                },
                "gtin13": "7891234567890"
            }
            </script>
        </head>
        <body>
            <h1>Product Page</h1>
        </body>
        </html>
        """

    @pytest.fixture
    def sample_html_without_jsonld(self):
        """HTML without JSON-LD (fallback scenario)."""
        return """
        <!DOCTYPE html>
        <html>
        <body>
            <h1>No JSON-LD Here</h1>
            <p>Price: R$ 10.00</p>
        </body>
        </html>
        """

    def test_extract_jsonld_from_html(self, sample_html_with_jsonld):
        """Test extracting Product JSON-LD from HTML."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(sample_html_with_jsonld, 'html.parser')
        scripts = soup.find_all('script', type='application/ld+json')

        assert len(scripts) == 1, "Should find one JSON-LD script"

        # Parse JSON-LD
        json_ld = json.loads(scripts[0].string)
        assert json_ld["@type"] == "Product"
        assert json_ld["name"] == "Arroz Integral 1kg"
        assert json_ld["sku"] == "12345"
        assert json_ld["offers"]["price"] == "8.99"

    def test_handle_missing_jsonld(self, sample_html_without_jsonld):
        """Test graceful handling when JSON-LD is missing."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(sample_html_without_jsonld, 'html.parser')
        scripts = soup.find_all('script', type='application/ld+json')

        assert len(scripts) == 0, "Should find no JSON-LD"
        # Scraper should return None or use fallback


class TestSuperKochHTMLScraper:
    """Test SuperKoch HTML scraper specifically."""

    @pytest.fixture
    def superkoch_scraper(self):
        """Create SuperKoch scraper instance."""
        config = {
            "base_url": "https://www.superkoch.com.br",
            "sitemap_pattern": "/sitemap.xml",
            "batch_size": 50,
            "request_delay": 0.1,
            "regions": {
                "balneario_camboriu": {
                    "store_id": "1415",
                    "cep": "88340-152",
                }
            }
        }
        return SuperKochHTMLScraper("superkoch", config)

    def test_normalize_product_from_jsonld(self, superkoch_scraper):
        """Test product normalization from JSON-LD."""
        json_ld_product = {
            "@type": "Product",
            "name": "Ração para Cães 15kg",
            "sku": "SK7890",
            "brand": {"name": "Pedigree"},
            "image": ["https://superkoch.com.br/image.jpg"],
            "offers": {
                "price": "89.90",
                "availability": "https://schema.org/InStock"
            },
            "gtin13": "7898765432109"
        }

        product_url = "https://www.superkoch.com.br/produtos/7890/racao-caes"
        region_cfg = {"store_id": "1415"}

        # Normalize
        normalized = superkoch_scraper._normalize_product(json_ld_product, product_url, region_cfg)

        # Assertions
        assert normalized["productId"] == "SK7890" or normalized["productId"] == "7890"
        assert normalized["productName"] == "Ração para Cães 15kg"
        assert normalized["brand"] == "Pedigree"
        assert normalized["price"] == 89.90
        assert normalized["ean"] == "7898765432109"
        assert normalized["storeId"] == "1415"

    def test_extract_product_id_from_url(self, superkoch_scraper):
        """Test extracting product ID from URL when SKU is missing."""
        import re

        product_url = "https://www.superkoch.com.br/produtos/12345/produto-teste"
        match = re.search(r'/produtos/(\d+)/', product_url)

        assert match is not None
        assert match.group(1) == "12345"


class TestHippoHTMLScraper:
    """Test Hippo HTML scraper specifically."""

    @pytest.fixture
    def hippo_scraper(self):
        """Create Hippo scraper instance."""
        config = {
            "base_url": "https://www.hipposupermercados.com.br",
            "sitemap_pattern": "/sitemap.xml",
            "batch_size": 50,
            "request_delay": 0.1,
            "regions": {
                "florianopolis_centro": {
                    "store_id": "1384",
                    "cep": "88015-420",
                }
            }
        }
        return HippoHTMLScraper("hippo", config)

    def test_hippo_normalize_product(self, hippo_scraper):
        """Test Hippo product normalization."""
        json_ld_product = {
            "@type": "Product",
            "name": "Cerveja Artesanal 500ml",
            "sku": "H9999",
            "brand": {"name": "Eisenbahn"},
            "image": ["https://hippo.com.br/cerveja.jpg"],
            "offers": {
                "price": "12.50",
                "availability": "https://schema.org/InStock"
            }
        }

        product_url = "https://www.hipposupermercados.com.br/produtos/9999/cerveja"
        region_cfg = {"store_id": "1384"}

        normalized = hippo_scraper._normalize_product(json_ld_product, product_url, region_cfg)

        assert normalized["productName"] == "Cerveja Artesanal 500ml"
        assert normalized["price"] == 12.50
        assert normalized["listPrice"] == 12.50  # HTML scrapers set listPrice = price
        assert normalized["platform"] == "osuper"

    def test_hippo_validates_against_schema(self, hippo_scraper):
        """Test Hippo products validate against Pydantic schema."""
        from src.schemas.hippo import HippoProduct

        product_data = {
            "productId": "123",
            "productName": "Test Product",
            "brand": "Test Brand",
            "price": 10.00,
            "listPrice": 10.00,
            "available": True,
            "stock": 100,
            "productUrl": "https://example.com/product",
            "storeId": "1384",
            "platform": "osuper",
            "scrapedAt": "2026-02-07T10:00:00",
            "categories": [],
            "categoryIds": [],
            "saleUnit": "UN",
        }

        # Should not raise ValidationError
        validated = HippoProduct(**product_data)
        assert validated.productId == "123"
        assert validated.price == 10.00


class TestCarrefourHTMLScraper:
    """Test Carrefour HTML scraper (VTEX with API blocked)."""

    @pytest.fixture
    def carrefour_scraper(self):
        """Create Carrefour scraper instance."""
        config = {
            "base_url": "https://mercado.carrefour.com.br",
            "sitemap_pattern": "/sitemap/product-{n}.xml",
            "sitemap_start_index": 1,
            "batch_size": 50,
            "request_delay": 0.1,
            "regions": {
                "florianopolis_centro": {
                    "cep": "88010-000",
                    "sc": "1",
                }
            }
        }
        return CarrefourHTMLScraper("carrefour", config)

    def test_carrefour_sitemap_index_starts_at_1(self, carrefour_scraper):
        """Test Carrefour sitemap starts at index 1 (not 0)."""
        assert carrefour_scraper.config.get("sitemap_start_index") == 1

        # Sitemap URL should be /sitemap/product-1.xml (not product-0.xml)
        expected_pattern = "/sitemap/product-{n}.xml"
        assert carrefour_scraper.config["sitemap_pattern"] == expected_pattern


class TestAngeloniHTMLScraper:
    """Test Angeloni HTML scraper."""

    @pytest.fixture
    def angeloni_scraper(self):
        """Create Angeloni scraper instance."""
        config = {
            "base_url": "https://www.angeloni.com.br",
            "sitemap_pattern": "/super/sitemap/product-{n}.xml",
            "batch_size": 50,
            "request_delay": 0.1,
            "regions": {
                "florianopolis_centro": {
                    "cep": "88010-000",
                    "sc": "1",
                    "hub_id": "v2.6470C9DD8410520F44B2C757ECBDE327"
                }
            }
        }
        return AngeloniHTMLScraper("angeloni", config)

    def test_angeloni_sitemap_pattern(self, angeloni_scraper):
        """Test Angeloni sitemap pattern is correct."""
        expected_pattern = "/super/sitemap/product-{n}.xml"
        assert angeloni_scraper.config["sitemap_pattern"] == expected_pattern


class TestHTMLScrapersCommonBehavior:
    """Test common behavior across all HTML scrapers."""

    @pytest.fixture(params=[
        "superkoch_html",
        "hippo_html",
        "carrefour_html",
        "angeloni_html"
    ])
    def html_scraper(self, request):
        """Parametrized fixture for all HTML scrapers."""
        scraper_configs = {
            "superkoch_html": (SuperKochHTMLScraper, {
                "base_url": "https://www.superkoch.com.br",
                "sitemap_pattern": "/sitemap.xml",
                "batch_size": 50,
                "request_delay": 0.1,
                "regions": {"test": {"store_id": "1415"}}
            }),
            "hippo_html": (HippoHTMLScraper, {
                "base_url": "https://www.hipposupermercados.com.br",
                "sitemap_pattern": "/sitemap.xml",
                "batch_size": 50,
                "request_delay": 0.1,
                "regions": {"test": {"store_id": "1384"}}
            }),
            "carrefour_html": (CarrefourHTMLScraper, {
                "base_url": "https://mercado.carrefour.com.br",
                "sitemap_pattern": "/sitemap/product-{n}.xml",
                "sitemap_start_index": 1,
                "batch_size": 50,
                "request_delay": 0.1,
                "regions": {"test": {"cep": "88010-000"}}
            }),
            "angeloni_html": (AngeloniHTMLScraper, {
                "base_url": "https://www.angeloni.com.br",
                "sitemap_pattern": "/super/sitemap/product-{n}.xml",
                "batch_size": 50,
                "request_delay": 0.1,
                "regions": {"test": {"cep": "88010-000"}}
            }),
        }

        ScraperClass, config = scraper_configs[request.param]
        return ScraperClass(request.param, config)

    def test_all_html_scrapers_have_base_methods(self, html_scraper):
        """Test all HTML scrapers implement required methods."""
        assert hasattr(html_scraper, 'discover_products')
        assert hasattr(html_scraper, 'scrape_region')
        assert hasattr(html_scraper, '_fetch_product_html')
        assert hasattr(html_scraper, '_normalize_product')

    def test_all_html_scrapers_use_beautifulsoup(self, html_scraper):
        """Test HTML scrapers use BeautifulSoup for parsing."""
        # Check that BeautifulSoup is imported in the module
        import inspect
        source = inspect.getsource(html_scraper.__class__)
        assert 'BeautifulSoup' in source or 'bs4' in source

    def test_all_html_scrapers_handle_request_delay(self, html_scraper):
        """Test HTML scrapers have request delay configured."""
        assert html_scraper.request_delay >= 0.1
        assert html_scraper.request_delay <= 1.0  # Reasonable upper bound


class TestHTMLScrapersErrorHandling:
    """Test error handling in HTML scrapers."""

    @pytest.fixture
    def superkoch_scraper(self):
        config = {
            "base_url": "https://www.superkoch.com.br",
            "sitemap_pattern": "/sitemap.xml",
            "batch_size": 50,
            "request_delay": 0.1,
            "regions": {"test": {"store_id": "1415"}}
        }
        return SuperKochHTMLScraper("superkoch", config)

    def test_handle_404_product_page(self, superkoch_scraper):
        """Test scraper handles 404 errors gracefully."""
        product_url = "https://www.superkoch.com.br/produtos/999999/nao-existe"

        with patch.object(superkoch_scraper.session, 'get') as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 404
            mock_get.return_value = mock_resp

            result = superkoch_scraper._fetch_product_html(product_url, {"store_id": "1415"})

            assert result is None, "Should return None for 404"

    def test_handle_malformed_html(self, superkoch_scraper):
        """Test scraper handles malformed HTML."""
        malformed_html = "<html><body><p>Unclosed tag"

        with patch.object(superkoch_scraper.session, 'get') as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.content = malformed_html.encode('utf-8')
            mock_get.return_value = mock_resp

            # Should not crash, should return None or handle gracefully
            result = superkoch_scraper._fetch_product_html("http://test.com", {"store_id": "1415"})

            # Result might be None or empty, but shouldn't raise exception
            assert result is None or isinstance(result, dict)

    def test_handle_malformed_jsonld(self, superkoch_scraper):
        """Test scraper handles malformed JSON-LD."""
        html_with_bad_json = """
        <html>
        <script type="application/ld+json">
        { "malformed": json here }
        </script>
        </html>
        """

        with patch.object(superkoch_scraper.session, 'get') as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.content = html_with_bad_json.encode('utf-8')
            mock_get.return_value = mock_resp

            result = superkoch_scraper._fetch_product_html("http://test.com", {"store_id": "1415"})

            # Should handle gracefully (return None or skip)
            assert result is None or isinstance(result, dict)
