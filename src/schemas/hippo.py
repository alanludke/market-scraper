"""
Pydantic schemas for Hippo Supermercados (Osuper platform) GraphQL responses.

These models validate GraphQL responses at runtime, ensuring data quality from the source.
Invalid products are logged and skipped, preventing corrupted data from reaching bronze layer.

Usage:
    from src.schemas.hippo import HippoProduct

    try:
        product = HippoProduct.parse_obj(normalized_data)
    except ValidationError as e:
        logger.error("Invalid product schema", error=str(e))
        metrics.increment("validation_errors")
"""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class HippoProduct(BaseModel):
    """
    Hippo Supermercados product data model (normalized from GraphQL).

    Fields are normalized to match common e-commerce patterns,
    making integration with DBT models easier.
    """
    # Core identifiers
    productId: str = Field(..., min_length=1, description="Product ID from Hippo")
    productName: str = Field(..., min_length=1, description="Product name/title")
    brand: Optional[str] = Field(None, description="Product brand")
    ean: Optional[str] = Field(None, description="GTIN/EAN barcode")

    # Pricing
    price: float = Field(..., gt=0, description="Current selling price (must be > 0)")
    listPrice: Optional[float] = Field(None, ge=0, description="Original list price")

    # Availability
    available: bool = Field(..., description="Whether product is in stock")
    stock: int = Field(..., ge=0, description="Available quantity in stock")

    # Media
    imageUrl: Optional[str] = Field(None, description="Product image URL")
    productUrl: str = Field(..., description="Product page URL")

    # Categorization
    categories: List[str] = Field(default_factory=list, description="Category names")
    categoryIds: List[str] = Field(default_factory=list, description="Category IDs")

    # Sale unit
    saleUnit: str = Field(default="UN", description="Sale unit (UN, KG, etc)")

    # Store context
    storeId: str = Field(..., description="Store ID for this product data")

    # Metadata
    platform: str = Field(default="osuper", description="E-commerce platform")
    scrapedAt: str = Field(..., description="ISO timestamp when scraped")

    @field_validator('imageUrl')
    @classmethod
    def validate_image_url(cls, v):
        """Ensure image URL is valid HTTPS."""
        if v and v.strip():
            # Ensure HTTPS for security
            if v.startswith("http://"):
                v = v.replace("http://", "https://", 1)
        return v

    @field_validator('productUrl')
    @classmethod
    def validate_product_url(cls, v):
        """Ensure product URL is valid."""
        if not v or not v.strip():
            raise ValueError("productUrl cannot be empty")
        return v

    @field_validator('listPrice')
    @classmethod
    def validate_list_price(cls, v, info):
        """Ensure listPrice >= price."""
        if v is not None and 'price' in info.data:
            price = info.data['price']
            if v < price:
                raise ValueError(
                    f"listPrice ({v}) cannot be less than price ({price})"
                )
        return v

    @field_validator('ean')
    @classmethod
    def validate_ean(cls, v):
        """Validate EAN format (8, 12, 13, or 14 digits)."""
        if v and v.strip():
            # Remove any non-digit characters
            digits = ''.join(c for c in v if c.isdigit())
            if digits and len(digits) not in [8, 12, 13, 14]:
                # Log warning but don't fail validation
                # (some products may have invalid EANs)
                pass
            return digits if digits else None
        return None

    class Config:
        extra = "allow"  # Allow extra fields for forward compatibility
        str_strip_whitespace = True  # Auto-strip strings
        validate_assignment = True  # Validate on assignment too
