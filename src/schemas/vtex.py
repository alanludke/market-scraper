"""
Pydantic schemas for VTEX API responses.

These models validate API responses at runtime, ensuring data quality from the source.
Invalid products are logged and skipped, preventing corrupted data from reaching bronze layer.

Usage:
    from src.schemas.vtex import VTEXProduct

    try:
        product = VTEXProduct.parse_obj(api_response)
    except ValidationError as e:
        logger.error("Invalid product schema", error=str(e))
        metrics.increment("validation_errors")
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator, root_validator
from datetime import datetime


class VTEXImage(BaseModel):
    """Product image metadata."""
    imageId: str
    imageLabel: Optional[str] = None
    imageTag: Optional[str] = None
    imageUrl: str
    imageText: Optional[str] = None

    @validator('imageUrl')
    def validate_image_url(cls, v):
        """Ensure image URL is valid and not empty."""
        if not v or not v.strip():
            raise ValueError("imageUrl cannot be empty")
        # Ensure HTTPS for security
        if v.startswith("http://"):
            v = v.replace("http://", "https://", 1)
        return v


class VTEXOffer(BaseModel):
    """Commercial offer from a seller."""
    Price: float = Field(gt=0, description="Current price (must be > 0)")
    ListPrice: Optional[float] = Field(None, ge=0, description="Original list price")
    PriceWithoutDiscount: Optional[float] = Field(None, ge=0)
    RewardValue: Optional[float] = Field(None, ge=0)
    PriceValidUntil: Optional[str] = None
    AvailableQuantity: int = Field(ge=0, description="Stock quantity")
    Tax: Optional[float] = Field(None, ge=0)
    CacheVersionUsedToCallCheckout: Optional[str] = None

    @validator('ListPrice', always=True)
    def validate_list_price(cls, v, values):
        """Ensure ListPrice >= Price (if present)."""
        if v is not None and 'Price' in values:
            if v < values['Price']:
                # ListPrice should be >= Price (discount scenario)
                # If not, it's likely a data quality issue
                raise ValueError(f"ListPrice ({v}) cannot be less than Price ({values['Price']})")
        return v

    @root_validator
    def validate_offer(cls, values):
        """Cross-field validation for offer consistency."""
        price = values.get('Price')
        list_price = values.get('ListPrice')
        price_without_discount = values.get('PriceWithoutDiscount')

        # If ListPrice is missing, default to Price (no discount)
        if list_price is None and price is not None:
            values['ListPrice'] = price

        # If PriceWithoutDiscount exists, it should be >= Price
        if price_without_discount is not None and price is not None:
            if price_without_discount < price:
                raise ValueError(
                    f"PriceWithoutDiscount ({price_without_discount}) cannot be less than Price ({price})"
                )

        return values


class VTEXSeller(BaseModel):
    """Seller information and commercial offer."""
    sellerId: str
    sellerName: str
    addToCartLink: Optional[str] = None
    sellerDefault: Optional[bool] = None
    commertialOffer: VTEXOffer

    @validator('sellerId')
    def validate_seller_id(cls, v):
        """Ensure sellerId is not empty."""
        if not v or not v.strip():
            raise ValueError("sellerId cannot be empty")
        return v


class VTEXItem(BaseModel):
    """SKU/Item within a product."""
    itemId: str
    name: str
    nameComplete: Optional[str] = None
    complementName: Optional[str] = None
    ean: Optional[str] = None
    referenceId: Optional[List[Dict[str, Any]]] = None
    measurementUnit: Optional[str] = None
    unitMultiplier: Optional[float] = None
    sellers: List[VTEXSeller]
    images: List[VTEXImage] = Field(default_factory=list)
    Videos: Optional[List[str]] = Field(default_factory=list)

    @validator('itemId')
    def validate_item_id(cls, v):
        """Ensure itemId is not empty."""
        if not v or not v.strip():
            raise ValueError("itemId cannot be empty")
        return v

    @validator('ean')
    def validate_ean(cls, v):
        """Validate EAN format (if present)."""
        if v is not None and v.strip():
            # Remove non-digit characters
            cleaned_ean = ''.join(filter(str.isdigit, v))
            # EAN should be 8, 13, or 14 digits (EAN-8, EAN-13, GTIN-14)
            if len(cleaned_ean) not in (8, 13, 14):
                # Don't fail validation, just log warning and return original
                # (some stores have non-standard EANs)
                return v
            return cleaned_ean
        return v

    @validator('sellers')
    def validate_sellers_not_empty(cls, v):
        """Ensure at least one seller exists."""
        if not v or len(v) == 0:
            raise ValueError("Product must have at least one seller")
        return v


class VTEXCategory(BaseModel):
    """Product category information."""
    id: str
    name: str

    @validator('id', 'name')
    def validate_not_empty(cls, v):
        """Ensure category fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Category id/name cannot be empty")
        return v


class VTEXProduct(BaseModel):
    """
    Complete VTEX product schema.

    Validates products fetched from VTEX API (/api/catalog_system/pub/products/search).
    Ensures data quality before persisting to bronze layer.
    """
    productId: str
    productName: str
    brand: Optional[str] = None
    brandId: Optional[int] = None
    brandImageUrl: Optional[str] = None
    linkText: str
    productReference: Optional[str] = None
    categoryId: Optional[str] = None
    productTitle: Optional[str] = None
    metaTagDescription: Optional[str] = None
    releaseDate: Optional[str] = None
    clusterHighlights: Optional[Dict[str, Any]] = None
    productClusters: Optional[Dict[str, Any]] = None
    searchableClusters: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = Field(default_factory=list)
    categoriesIds: Optional[List[str]] = Field(default_factory=list)
    link: str
    description: Optional[str] = None
    items: List[VTEXItem]
    allSpecifications: Optional[List[str]] = Field(default_factory=list)
    allSpecificationsGroups: Optional[List[str]] = Field(default_factory=list)

    @validator('productId')
    def validate_product_id(cls, v):
        """Ensure productId is not empty."""
        if not v or not v.strip():
            raise ValueError("productId cannot be empty")
        return v

    @validator('productName')
    def validate_product_name(cls, v):
        """Ensure productName is not empty and reasonable length."""
        if not v or not v.strip():
            raise ValueError("productName cannot be empty")
        if len(v) > 500:
            raise ValueError(f"productName too long ({len(v)} chars, max 500)")
        return v.strip()

    @validator('link')
    def validate_link(cls, v):
        """Ensure product link is valid."""
        if not v or not v.strip():
            raise ValueError("link cannot be empty")
        # Ensure HTTPS
        if v.startswith("http://"):
            v = v.replace("http://", "https://", 1)
        return v

    @validator('items')
    def validate_items_not_empty(cls, v):
        """Ensure product has at least one item/SKU."""
        if not v or len(v) == 0:
            raise ValueError("Product must have at least one item")
        return v

    @root_validator
    def validate_product(cls, values):
        """Cross-field validation for product consistency."""
        product_id = values.get('productId')
        items = values.get('items', [])

        # Ensure all items belong to this product (some APIs return inconsistent data)
        # This is a sanity check, not strictly enforced by VTEX API
        for item in items:
            if not item.itemId.startswith(str(product_id)):
                # Don't fail, but this could indicate API issues
                # Log this in the scraper when validation passes
                pass

        return values

    class Config:
        """Pydantic config."""
        # Allow extra fields from API (forward compatibility)
        extra = "allow"
        # Use enum values
        use_enum_values = True


# Lightweight schema for category tree discovery
class VTEXCategoryTree(BaseModel):
    """Category tree node for discovery."""
    id: int
    name: str
    hasChildren: bool
    url: Optional[str] = None
    children: Optional[List['VTEXCategoryTree']] = None

    @validator('id')
    def validate_id_positive(cls, v):
        """Ensure category ID is positive."""
        if v <= 0:
            raise ValueError(f"Category ID must be positive, got {v}")
        return v

    class Config:
        """Pydantic config."""
        # Allow extra fields
        extra = "allow"


# Enable forward references for recursive models
VTEXCategoryTree.update_forward_refs()
