"""
Pydantic schemas for OpenFoodFacts API responses.

OpenFoodFacts is a global food products database with nutritional information,
barcodes (EANs), and product attributes.

API Documentation: https://wiki.openfoodfacts.org/API/Read/Product
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class OpenFoodFactsNutriments(BaseModel):
    """Nutritional information per 100g."""

    energy_100g: Optional[float] = Field(None, alias='energy-kcal_100g')
    proteins_100g: Optional[float] = None
    fat_100g: Optional[float] = None
    carbohydrates_100g: Optional[float] = None
    sugars_100g: Optional[float] = None
    fiber_100g: Optional[float] = None
    salt_100g: Optional[float] = None
    sodium_100g: Optional[float] = None

    class Config:
        extra = "allow"  # Allow additional nutritional fields
        populate_by_name = True  # Support both field name and alias


class OpenFoodFactsProduct(BaseModel):
    """
    OpenFoodFacts product schema.

    Represents a product from the OpenFoodFacts API with EAN barcode,
    product name, brand, categories, and nutritional information.
    """

    code: str = Field(..., description="EAN barcode (8, 13, or 14 digits)")
    product_name: Optional[str] = None
    brands: Optional[str] = None
    categories: Optional[str] = None
    countries: Optional[str] = None
    quantity: Optional[str] = Field(None, description="Net weight (e.g., '500g', '1.5kg')")
    nutriscore_grade: Optional[str] = Field(None, description="Nutriscore rating (A-E)")
    nutriments: Optional[OpenFoodFactsNutriments] = None

    # Additional useful fields
    ingredients_text: Optional[str] = None
    allergens: Optional[str] = None
    labels: Optional[str] = None
    packaging: Optional[str] = None
    image_url: Optional[str] = None

    @field_validator('nutriscore_grade')
    @classmethod
    def validate_nutriscore(cls, v):
        """Validate and normalize nutriscore grade to lowercase a-e."""
        if v and v.lower() not in ['a', 'b', 'c', 'd', 'e']:
            return None  # Invalid grade = None
        return v.lower() if v else None

    @field_validator('code')
    @classmethod
    def validate_ean(cls, v):
        """Validate EAN barcode length."""
        if not v:
            raise ValueError("EAN code cannot be empty")

        # Valid EAN lengths: 8, 13, 14
        if len(v) not in [8, 13, 14]:
            raise ValueError(f"Invalid EAN length: {len(v)}. Expected 8, 13, or 14 digits")

        return v

    class Config:
        extra = "allow"  # Forward compatibility - allow extra fields from API
        populate_by_name = True
