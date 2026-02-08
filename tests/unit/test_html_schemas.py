"""
Unit tests for HTML scraper Pydantic schemas.

Tests schema validation for:
- SuperKochProduct (Osuper platform)
- HippoProduct (Osuper platform)

Run with: pytest tests/unit/test_html_schemas.py -v
"""

import pytest
from pydantic import ValidationError

from src.schemas.superkoch import SuperKochProduct
from src.schemas.hippo import HippoProduct


# ─────────────────────────────────────────────────────────────────────
# Osuper Platform Product Tests (SuperKoch and Hippo use same base schema)
# ─────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────
# SuperKochProduct Tests
# ─────────────────────────────────────────────────────────────────────

class TestSuperKochProductSchema:
    """Test SuperKochProduct Pydantic schema."""

    def test_valid_super_koch_product(self):
        """Test valid Super Koch product passes validation."""
        data = {
            "productId": "400",
            "productName": "Super Koch Product",
            "price": 40.00,
            "listPrice": 50.00,
            "available": True,
            "stock": 15,
            "brand": "Koch Brand",
            "ean": "1122334455667",
            "imageUrl": "https://example.com/koch.jpg",
            "productUrl": "https://superkoch.com.br/product/400",
            "storeId": "1",
            "scrapedAt": "2026-02-07T20:00:00",
            "platform": "osuper"
        }

        product = SuperKochProduct(**data)
        assert product.productId == "400"
        assert product.platform == "osuper"
        assert product.price == 40.00

    def test_listprice_less_than_price_fails(self):
        """Test listPrice cannot be less than price."""
        data = {
            "productId": "400",
            "productName": "Test Product",
            "price": 50.00,
            "listPrice": 40.00,  # Less than price - should fail validation
            "available": True,
            "stock": 10,
            "productUrl": "https://superkoch.com.br/product/400",
            "storeId": "1",
            "scrapedAt": "2026-02-07T20:00:00",
            "platform": "osuper"
        }

        # Should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            SuperKochProduct(**data)

        assert "listPrice" in str(exc_info.value)

    def test_platform_default_value(self):
        """Test platform defaults to osuper."""
        data = {
            "productId": "400",
            "productName": "Test Product",
            "price": 10.00,
            "available": True,
            "stock": 10,
            "productUrl": "https://superkoch.com.br/product/400",
            "storeId": "1",
            "scrapedAt": "2026-02-07T20:00:00"
        }

        product = SuperKochProduct(**data)
        assert product.platform == "osuper"

    def test_zero_stock_valid(self):
        """Test zero stock is valid (out of stock)."""
        data = {
            "productId": "400",
            "productName": "Test Product",
            "price": 10.00,
            "available": False,
            "stock": 0,  # Zero stock
            "productUrl": "https://superkoch.com.br/product/400",
            "storeId": "1",
            "scrapedAt": "2026-02-07T20:00:00",
            "platform": "osuper"
        }

        product = SuperKochProduct(**data)
        assert product.stock == 0
        assert product.available is False


# ─────────────────────────────────────────────────────────────────────
# HippoProduct Tests
# ─────────────────────────────────────────────────────────────────────

class TestHippoProductSchema:
    """Test HippoProduct Pydantic schema."""

    def test_valid_hippo_product(self):
        """Test valid Hippo product passes validation."""
        data = {
            "productId": "500",
            "productName": "Hippo Product",
            "price": 60.00,
            "listPrice": 70.00,
            "available": True,
            "stock": 8,
            "brand": "Hippo Brand",
            "ean": "9988776655443",
            "imageUrl": "https://example.com/hippo.jpg",
            "productUrl": "https://hippo.com.br/product/500",
            "storeId": "1384",
            "scrapedAt": "2026-02-07T20:00:00",
            "platform": "osuper"
        }

        product = HippoProduct(**data)
        assert product.productId == "500"
        assert product.platform == "osuper"
        assert product.price == 60.00

    def test_optional_fields_nullable(self):
        """Test optional fields can be None."""
        data = {
            "productId": "500",
            "productName": "Test Product",
            "price": 10.00,
            "available": True,
            "stock": 5,
            "productUrl": "https://hippo.com.br/product/500",
            "storeId": "1384",
            "scrapedAt": "2026-02-07T20:00:00",
            "platform": "osuper"
        }

        product = HippoProduct(**data)
        assert product.listPrice is None
        assert product.brand is None
        assert product.ean is None
        assert product.imageUrl is None

    def test_platform_default_value(self):
        """Test platform defaults to osuper."""
        data = {
            "productId": "500",
            "productName": "Test Product",
            "price": 10.00,
            "available": True,
            "stock": 5,
            "productUrl": "https://hippo.com.br/product/500",
            "storeId": "1384",
            "scrapedAt": "2026-02-07T20:00:00"
        }

        product = HippoProduct(**data)
        assert product.platform == "osuper"

    def test_empty_product_id_fails(self):
        """Test empty product ID fails validation."""
        data = {
            "productId": "",  # Invalid: empty
            "productName": "Test Product",
            "price": 10.00,
            "available": True,
            "stock": 5,
            "productUrl": "https://hippo.com.br/product/500",
            "storeId": "1384",
            "scrapedAt": "2026-02-07T20:00:00"
        }

        with pytest.raises(ValidationError) as exc_info:
            HippoProduct(**data)

        assert "productId" in str(exc_info.value)


# ─────────────────────────────────────────────────────────────────────
# Schema Data Transformation Tests
# ─────────────────────────────────────────────────────────────────────

class TestSchemaDataTransformation:
    """Test schema data transformations and coercion."""

    def test_string_to_float_coercion(self):
        """Test string prices are coerced to float."""
        data = {
            "productId": "100",
            "productName": "Test Product",
            "price": "10.50",  # String instead of float
            "available": True,
            "stock": 10,
            "productUrl": "https://hippo.com.br/product/100",
            "storeId": "1",
            "scrapedAt": "2026-02-07T20:00:00",
            "platform": "osuper"
        }

        product = HippoProduct(**data)
        assert isinstance(product.price, float)
        assert product.price == 10.50

    def test_string_to_int_coercion(self):
        """Test string stock is coerced to int."""
        data = {
            "productId": "100",
            "productName": "Test Product",
            "price": 10.00,
            "available": True,
            "stock": "25",  # String instead of int
            "productUrl": "https://superkoch.com.br/product/100",
            "storeId": "1",
            "scrapedAt": "2026-02-07T20:00:00",
            "platform": "osuper"
        }

        product = SuperKochProduct(**data)
        assert isinstance(product.stock, int)
        assert product.stock == 25


# ─────────────────────────────────────────────────────────────────────
# Schema Edge Cases Tests
# ─────────────────────────────────────────────────────────────────────

class TestSchemaEdgeCases:
    """Test schema edge cases and boundary conditions."""

    def test_very_long_product_name(self):
        """Test very long product names are accepted."""
        data = {
            "productId": "100",
            "productName": "A" * 1000,  # Very long name
            "price": 10.00,
            "available": True,
            "stock": 10,
            "productUrl": "https://hippo.com.br/product/100",
            "storeId": "1",
            "scrapedAt": "2026-02-07T20:00:00",
            "platform": "osuper"
        }

        product = HippoProduct(**data)
        assert len(product.productName) == 1000

    def test_very_high_price(self):
        """Test very high prices are accepted."""
        data = {
            "productId": "100",
            "productName": "Luxury Product",
            "price": 999999.99,  # Very high price
            "available": True,
            "stock": 1,
            "productUrl": "https://superkoch.com.br/product/100",
            "storeId": "1",
            "scrapedAt": "2026-02-07T20:00:00",
            "platform": "osuper"
        }

        product = SuperKochProduct(**data)
        assert product.price == 999999.99

    def test_very_small_price(self):
        """Test very small positive prices are accepted."""
        data = {
            "productId": "100",
            "productName": "Cheap Product",
            "price": 0.01,  # Very small price
            "available": True,
            "stock": 100,
            "productUrl": "https://hippo.com.br/product/100",
            "storeId": "1",
            "scrapedAt": "2026-02-07T20:00:00",
            "platform": "osuper"
        }

        product = HippoProduct(**data)
        assert product.price == 0.01

    def test_empty_ean_normalized(self):
        """Test empty EAN is normalized to None."""
        data = {
            "productId": "100",
            "productName": "Test Product",
            "price": 10.00,
            "available": True,
            "stock": 10,
            "ean": "",  # Empty string
            "productUrl": "https://superkoch.com.br/product/100",
            "storeId": "1",
            "scrapedAt": "2026-02-07T20:00:00",
            "platform": "osuper"
        }

        product = SuperKochProduct(**data)
        assert product.ean is None


# ─────────────────────────────────────────────────────────────────────
# Batch Validation Tests
# ─────────────────────────────────────────────────────────────────────

class TestSchemaBatchValidation:
    """Test validating batches of products."""

    def test_validate_batch_of_products(self):
        """Test validating a batch of products."""
        products_data = [
            {
                "productId": f"{i}",
                "productName": f"Product {i}",
                "price": float(i * 10),
                "available": True,
                "stock": i * 5,
                "productUrl": f"https://hippo.com.br/product/{i}",
                "storeId": "1",
                "scrapedAt": "2026-02-07T20:00:00",
                "platform": "osuper"
            }
            for i in range(1, 11)
        ]

        products = [HippoProduct(**p) for p in products_data]
        assert len(products) == 10
        assert all(isinstance(p, HippoProduct) for p in products)

    def test_batch_with_some_invalid_products(self):
        """Test batch validation with some invalid products."""
        products_data = [
            {"productId": "1", "productName": "Valid", "price": 10.0, "available": True, "stock": 10, "productUrl": "https://hippo.com.br/1", "storeId": "1", "scrapedAt": "2026-02-07T20:00:00", "platform": "osuper"},
            {"productId": "", "productName": "Invalid", "price": 10.0, "available": True, "stock": 10, "productUrl": "https://hippo.com.br/2", "storeId": "1", "scrapedAt": "2026-02-07T20:00:00", "platform": "osuper"},  # Invalid ID
            {"productId": "3", "productName": "Valid", "price": 30.0, "available": True, "stock": 10, "productUrl": "https://hippo.com.br/3", "storeId": "1", "scrapedAt": "2026-02-07T20:00:00", "platform": "osuper"},
        ]

        valid_products = []
        invalid_count = 0

        for data in products_data:
            try:
                product = HippoProduct(**data)
                valid_products.append(product)
            except ValidationError:
                invalid_count += 1

        assert len(valid_products) == 2
        assert invalid_count == 1

    def test_mixed_osuper_stores_batch(self):
        """Test batch with mixed Osuper platform stores (SuperKoch and Hippo)."""
        products_data = [
            {"productId": "1", "productName": "SuperKoch Product", "price": 30.0, "available": True, "stock": 20, "productUrl": "https://superkoch.com.br/1", "storeId": "1", "scrapedAt": "2026-02-07T20:00:00", "platform": "osuper"},
            {"productId": "2", "productName": "Hippo Product", "price": 40.0, "available": True, "stock": 25, "productUrl": "https://hippo.com.br/2", "storeId": "1384", "scrapedAt": "2026-02-07T20:00:00", "platform": "osuper"},
        ]

        products = []
        for data in products_data:
            if "koch" in data["productName"].lower():
                products.append(SuperKochProduct(**data))
            else:
                products.append(HippoProduct(**data))

        assert len(products) == 2
        assert isinstance(products[0], SuperKochProduct)
        assert isinstance(products[1], HippoProduct)


if __name__ == "__main__":
    # CLI usage: python tests/unit/test_html_schemas.py
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
