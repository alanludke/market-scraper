"""
Unit tests for Pydantic VTEX schemas (Phase 2).

Tests validate that:
1. Valid VTEX API responses pass validation
2. Invalid data is properly rejected
3. Data transformations work correctly (e.g., EAN cleaning, HTTPS enforcement)
4. Cross-field validation works (e.g., ListPrice >= Price)

Run with: pytest tests/unit/test_schemas.py -v
"""

import pytest
from pydantic import ValidationError

from src.schemas.vtex import (
    VTEXProduct,
    VTEXItem,
    VTEXSeller,
    VTEXOffer,
    VTEXImage,
    VTEXCategory,
    VTEXCategoryTree,
)


# ─────────────────────────────────────────────────────────────────────
# VTEXOffer Tests
# ─────────────────────────────────────────────────────────────────────

def test_offer_valid():
    """Test that a valid offer passes validation."""
    offer_data = {
        "Price": 10.50,
        "ListPrice": 12.00,
        "AvailableQuantity": 100,
    }
    offer = VTEXOffer.parse_obj(offer_data)
    assert offer.Price == 10.50
    assert offer.ListPrice == 12.00
    assert offer.AvailableQuantity == 100


def test_offer_price_must_be_positive():
    """Test that Price must be > 0."""
    offer_data = {
        "Price": 0,
        "AvailableQuantity": 100,
    }
    with pytest.raises(ValidationError) as exc_info:
        VTEXOffer.parse_obj(offer_data)

    errors = exc_info.value.errors()
    assert any(e['loc'] == ('Price',) for e in errors)


def test_offer_list_price_defaults_to_price():
    """Test that ListPrice defaults to Price if missing."""
    offer_data = {
        "Price": 10.50,
        "AvailableQuantity": 100,
    }
    offer = VTEXOffer.parse_obj(offer_data)
    assert offer.ListPrice == 10.50  # Should default to Price


def test_offer_list_price_cannot_be_less_than_price():
    """Test that ListPrice >= Price validation works."""
    offer_data = {
        "Price": 12.00,
        "ListPrice": 10.00,  # Invalid: ListPrice < Price
        "AvailableQuantity": 100,
    }
    with pytest.raises(ValidationError) as exc_info:
        VTEXOffer.parse_obj(offer_data)

    errors = exc_info.value.errors()
    assert any('ListPrice' in str(e) for e in errors)


# ─────────────────────────────────────────────────────────────────────
# VTEXImage Tests
# ─────────────────────────────────────────────────────────────────────

def test_image_valid():
    """Test that a valid image passes validation."""
    image_data = {
        "imageId": "123",
        "imageUrl": "https://example.com/image.jpg",
    }
    image = VTEXImage.parse_obj(image_data)
    assert image.imageId == "123"
    assert image.imageUrl == "https://example.com/image.jpg"


def test_image_url_empty_fails():
    """Test that empty imageUrl fails validation."""
    image_data = {
        "imageId": "123",
        "imageUrl": "",
    }
    with pytest.raises(ValidationError):
        VTEXImage.parse_obj(image_data)


def test_image_url_http_converted_to_https():
    """Test that HTTP URLs are upgraded to HTTPS."""
    image_data = {
        "imageId": "123",
        "imageUrl": "http://example.com/image.jpg",
    }
    image = VTEXImage.parse_obj(image_data)
    assert image.imageUrl == "https://example.com/image.jpg"


# ─────────────────────────────────────────────────────────────────────
# VTEXSeller Tests
# ─────────────────────────────────────────────────────────────────────

def test_seller_valid():
    """Test that a valid seller passes validation."""
    seller_data = {
        "sellerId": "1",
        "sellerName": "Test Seller",
        "commertialOffer": {
            "Price": 10.50,
            "AvailableQuantity": 100,
        }
    }
    seller = VTEXSeller.parse_obj(seller_data)
    assert seller.sellerId == "1"
    assert seller.sellerName == "Test Seller"
    assert seller.commertialOffer.Price == 10.50


def test_seller_id_cannot_be_empty():
    """Test that sellerId cannot be empty."""
    seller_data = {
        "sellerId": "",
        "sellerName": "Test Seller",
        "commertialOffer": {
            "Price": 10.50,
            "AvailableQuantity": 100,
        }
    }
    with pytest.raises(ValidationError):
        VTEXSeller.parse_obj(seller_data)


# ─────────────────────────────────────────────────────────────────────
# VTEXItem Tests
# ─────────────────────────────────────────────────────────────────────

def test_item_valid():
    """Test that a valid item passes validation."""
    item_data = {
        "itemId": "123",
        "name": "Test Product",
        "ean": "1234567890123",
        "sellers": [
            {
                "sellerId": "1",
                "sellerName": "Test Seller",
                "commertialOffer": {
                    "Price": 10.50,
                    "AvailableQuantity": 100,
                }
            }
        ],
    }
    item = VTEXItem.parse_obj(item_data)
    assert item.itemId == "123"
    assert item.name == "Test Product"
    assert item.ean == "1234567890123"
    assert len(item.sellers) == 1


def test_item_ean_cleaning():
    """Test that EAN is cleaned (non-digits removed)."""
    item_data = {
        "itemId": "123",
        "name": "Test Product",
        "ean": "1234-5678-90123",  # Has dashes
        "sellers": [
            {
                "sellerId": "1",
                "sellerName": "Test Seller",
                "commertialOffer": {
                    "Price": 10.50,
                    "AvailableQuantity": 100,
                }
            }
        ],
    }
    item = VTEXItem.parse_obj(item_data)
    assert item.ean == "1234567890123"  # Cleaned


def test_item_must_have_at_least_one_seller():
    """Test that items must have at least one seller."""
    item_data = {
        "itemId": "123",
        "name": "Test Product",
        "sellers": [],  # Empty sellers
    }
    with pytest.raises(ValidationError) as exc_info:
        VTEXItem.parse_obj(item_data)

    errors = exc_info.value.errors()
    assert any('sellers' in str(e) for e in errors)


# ─────────────────────────────────────────────────────────────────────
# VTEXProduct Tests
# ─────────────────────────────────────────────────────────────────────

def test_product_valid():
    """Test that a valid product passes validation."""
    product_data = {
        "productId": "1",
        "productName": "Test Product",
        "linkText": "test-product",
        "link": "https://example.com/test-product",
        "items": [
            {
                "itemId": "123",
                "name": "Test Product SKU",
                "sellers": [
                    {
                        "sellerId": "1",
                        "sellerName": "Test Seller",
                        "commertialOffer": {
                            "Price": 10.50,
                            "AvailableQuantity": 100,
                        }
                    }
                ],
            }
        ],
    }
    product = VTEXProduct.parse_obj(product_data)
    assert product.productId == "1"
    assert product.productName == "Test Product"
    assert len(product.items) == 1


def test_product_name_cannot_be_empty():
    """Test that productName cannot be empty."""
    product_data = {
        "productId": "1",
        "productName": "",
        "linkText": "test-product",
        "link": "https://example.com/test-product",
        "items": [
            {
                "itemId": "123",
                "name": "Test Product SKU",
                "sellers": [
                    {
                        "sellerId": "1",
                        "sellerName": "Test Seller",
                        "commertialOffer": {
                            "Price": 10.50,
                            "AvailableQuantity": 100,
                        }
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValidationError):
        VTEXProduct.parse_obj(product_data)


def test_product_name_too_long():
    """Test that productName cannot exceed 500 chars."""
    product_data = {
        "productId": "1",
        "productName": "A" * 501,  # 501 chars
        "linkText": "test-product",
        "link": "https://example.com/test-product",
        "items": [
            {
                "itemId": "123",
                "name": "Test Product SKU",
                "sellers": [
                    {
                        "sellerId": "1",
                        "sellerName": "Test Seller",
                        "commertialOffer": {
                            "Price": 10.50,
                            "AvailableQuantity": 100,
                        }
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValidationError):
        VTEXProduct.parse_obj(product_data)


def test_product_link_http_converted_to_https():
    """Test that HTTP links are upgraded to HTTPS."""
    product_data = {
        "productId": "1",
        "productName": "Test Product",
        "linkText": "test-product",
        "link": "http://example.com/test-product",  # HTTP
        "items": [
            {
                "itemId": "123",
                "name": "Test Product SKU",
                "sellers": [
                    {
                        "sellerId": "1",
                        "sellerName": "Test Seller",
                        "commertialOffer": {
                            "Price": 10.50,
                            "AvailableQuantity": 100,
                        }
                    }
                ],
            }
        ],
    }
    product = VTEXProduct.parse_obj(product_data)
    assert product.link == "https://example.com/test-product"


def test_product_must_have_at_least_one_item():
    """Test that products must have at least one item."""
    product_data = {
        "productId": "1",
        "productName": "Test Product",
        "linkText": "test-product",
        "link": "https://example.com/test-product",
        "items": [],  # Empty items
    }
    with pytest.raises(ValidationError) as exc_info:
        VTEXProduct.parse_obj(product_data)

    errors = exc_info.value.errors()
    assert any('items' in str(e) for e in errors)


# ─────────────────────────────────────────────────────────────────────
# VTEXCategoryTree Tests
# ─────────────────────────────────────────────────────────────────────

def test_category_tree_valid():
    """Test that a valid category tree passes validation."""
    category_data = {
        "id": 1,
        "name": "Electronics",
        "hasChildren": True,
        "url": "/electronics",
        "children": [
            {
                "id": 2,
                "name": "Computers",
                "hasChildren": False,
            }
        ],
    }
    category = VTEXCategoryTree.parse_obj(category_data)
    assert category.id == 1
    assert category.name == "Electronics"
    assert category.hasChildren is True
    assert len(category.children) == 1


def test_category_tree_id_must_be_positive():
    """Test that category ID must be positive."""
    category_data = {
        "id": 0,
        "name": "Electronics",
        "hasChildren": False,
    }
    with pytest.raises(ValidationError):
        VTEXCategoryTree.parse_obj(category_data)


# ─────────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────────

def test_full_product_response():
    """Test a realistic full product response from VTEX API."""
    product_data = {
        "productId": "100",
        "productName": "Arroz Integral Tio João 1kg",
        "brand": "Tio João",
        "linkText": "arroz-integral-tio-joao-1kg",
        "link": "http://www.bistek.com.br/arroz-integral-tio-joao-1kg/p",
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
                        "imageUrl": "http://bistek.vteximg.com.br/arquivos/arroz.jpg",
                    }
                ],
            }
        ],
    }

    product = VTEXProduct.parse_obj(product_data)

    # Validate main fields
    assert product.productId == "100"
    assert product.productName == "Arroz Integral Tio João 1kg"

    # Validate HTTPS conversion
    assert product.link.startswith("https://")
    assert product.items[0].images[0].imageUrl.startswith("https://")

    # Validate offer
    offer = product.items[0].sellers[0].commertialOffer
    assert offer.Price == 8.99
    assert offer.ListPrice == 10.50
    assert offer.ListPrice >= offer.Price  # Cross-field validation


if __name__ == "__main__":
    # CLI usage: python tests/unit/test_schemas.py
    pytest.main([__file__, "-v", "--tb=short"])
