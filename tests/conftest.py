"""
Shared pytest fixtures for market_scraper tests.

Provides common test fixtures like temporary databases, mock API responses,
and test configurations.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock
import duckdb


# ─────────────────────────────────────────────────────────────────────
# Database Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_db():
    """Create a temporary DuckDB for testing."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ─────────────────────────────────────────────────────────────────────
# Mock API Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_vtex_product():
    """Sample VTEX product response."""
    return {
        "productId": "100",
        "productName": "Arroz Integral Tio João 1kg",
        "brand": "Tio João",
        "linkText": "arroz-integral-tio-joao-1kg",
        "link": "https://www.bistek.com.br/arroz-integral-tio-joao-1kg/p",
        "categoryId": "3",
        "items": [
            {
                "itemId": "101",
                "name": "Arroz Integral Tio João 1kg",
                "ean": "7891234567890",
                "sellers": [
                    {
                        "sellerId": "1",
                        "sellerName": "Bistek",
                        "commertialOffer": {
                            "Price": 8.99,
                            "ListPrice": 10.50,
                            "AvailableQuantity": 150,
                        }
                    }
                ],
                "images": [
                    {
                        "imageId": "img-1",
                        "imageUrl": "https://bistek.vteximg.com.br/arquivos/arroz.jpg",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def mock_vtex_invalid_product():
    """Sample VTEX product with validation errors."""
    return {
        "productId": "200",
        "productName": "",  # Invalid: empty name
        "linkText": "invalid-product",
        "link": "https://example.com/invalid",
        "items": [
            {
                "itemId": "201",
                "name": "Invalid Product",
                "sellers": [
                    {
                        "sellerId": "1",
                        "sellerName": "Test Seller",
                        "commertialOffer": {
                            "Price": -5.0,  # Invalid: negative price
                            "AvailableQuantity": 100,
                        }
                    }
                ],
            }
        ],
    }


@pytest.fixture
def mock_vtex_category_tree():
    """Sample VTEX category tree response."""
    return [
        {
            "id": 1,
            "name": "Alimentos",
            "hasChildren": True,
            "children": [
                {
                    "id": 2,
                    "name": "Arroz e Feijão",
                    "hasChildren": False,
                }
            ]
        },
        {
            "id": 3,
            "name": "Bebidas",
            "hasChildren": False,
        }
    ]


@pytest.fixture
def mock_requests_session():
    """Mock requests.Session for API testing."""
    session = Mock()

    # Mock successful response
    response = Mock()
    response.status_code = 200
    response.json.return_value = []

    session.get.return_value = response
    session.cookies = MagicMock()

    return session


# ─────────────────────────────────────────────────────────────────────
# Configuration Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_store_config():
    """Sample store configuration for testing."""
    return {
        "base_url": "https://www.bistek.com.br",
        "discovery": "sitemap",
        "global_discovery": True,
        "cookie_domain": ".bistek.com.br",
        "batch_size": 50,
        "request_delay": 0.5,
        "regions": {
            "florianopolis_costeira": {
                "cep": "88095-000",
                "sc": "1",
                "name": "Florianópolis - Costeira"
            },
            "florianopolis_santa_monica": {
                "cep": "88035-100",
                "sc": "1",
                "name": "Florianópolis - Santa Mônica"
            }
        }
    }


@pytest.fixture
def sample_giassi_config():
    """Sample Giassi config (global_discovery=false mode)."""
    return {
        "base_url": "https://www.giassi.com.br",
        "discovery": "category_tree",
        "global_discovery": False,
        "cookie_domain": ".giassi.com.br",
        "batch_size": 50,
        "request_delay": 0.5,
        "regions": {
            "florianopolis_costeira": {
                "cep": "88095-000",
                "sc": "1",
                "name": "Florianópolis - Costeira"
            }
        }
    }


# ─────────────────────────────────────────────────────────────────────
# Metrics Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def metrics_collector(temp_db):
    """Create a fresh MetricsCollector for testing."""
    from src.observability.metrics import MetricsCollector
    return MetricsCollector(db_path=temp_db)


# ─────────────────────────────────────────────────────────────────────
# Test Data Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_products_batch():
    """Sample batch of products for testing."""
    return [
        {
            "productId": str(i),
            "productName": f"Product {i}",
            "linkText": f"product-{i}",
            "link": f"https://example.com/product-{i}",
            "items": [
                {
                    "itemId": f"{i}01",
                    "name": f"Product {i} SKU",
                    "sellers": [
                        {
                            "sellerId": "1",
                            "sellerName": "Test Seller",
                            "commertialOffer": {
                                "Price": 10.0 + i,
                                "ListPrice": 12.0 + i,
                                "AvailableQuantity": 100,
                            }
                        }
                    ],
                }
            ],
        }
        for i in range(10)
    ]


# ─────────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_metrics_singleton():
    """Reset global metrics collector singleton between tests."""
    import src.observability.metrics as metrics_module
    metrics_module._metrics_instance = None
    yield
    metrics_module._metrics_instance = None
