"""
Integration tests for hot-deals validation.

Ensures that hot-deals (promotional products) are real and legitimate:
- Minimum discount threshold (e.g., 20%+)
- Price consistency (listPrice > price)
- No fake/inflated prices
- Temporal consistency (deals persist across scrapes)
"""

import pytest
import pandas as pd
import duckdb
from pathlib import Path
from datetime import datetime, timedelta


class TestHotDealsValidation:
    """Test suite for validating hot-deals quality."""

    @pytest.fixture
    def bronze_products(self, temp_dir):
        """Sample bronze layer products with various deal scenarios."""
        products = [
            # Real hot-deal (40% discount)
            {
                "productId": "1001",
                "productName": "Arroz Integral 5kg",
                "price": 15.00,
                "listPrice": 25.00,
                "brand": "Tio João",
                "scrapedAt": "2026-02-07T10:00:00",
                "store": "bistek",
            },
            # Modest discount (10% - not a hot-deal)
            {
                "productId": "1002",
                "productName": "Feijão Preto 1kg",
                "price": 9.00,
                "listPrice": 10.00,
                "brand": "Camil",
                "scrapedAt": "2026-02-07T10:00:00",
                "store": "bistek",
            },
            # Suspicious deal (200% discount - likely fake)
            {
                "productId": "1003",
                "productName": "Óleo de Soja 900ml",
                "price": 5.00,
                "listPrice": 15.00,
                "brand": "Liza",
                "scrapedAt": "2026-02-07T10:00:00",
                "store": "bistek",
            },
            # Invalid: price > listPrice (data quality issue)
            {
                "productId": "1004",
                "productName": "Açúcar Cristal 1kg",
                "price": 8.00,
                "listPrice": 6.00,
                "brand": "União",
                "scrapedAt": "2026-02-07T10:00:00",
                "store": "bistek",
            },
            # No discount (regular price)
            {
                "productId": "1005",
                "productName": "Café 500g",
                "price": 12.00,
                "listPrice": 12.00,
                "brand": "Pilão",
                "scrapedAt": "2026-02-07T10:00:00",
                "store": "bistek",
            },
            # Good hot-deal (25% discount)
            {
                "productId": "1006",
                "productName": "Leite Integral 1L",
                "price": 3.75,
                "listPrice": 5.00,
                "brand": "Tirol",
                "scrapedAt": "2026-02-07T10:00:00",
                "store": "bistek",
            },
        ]

        df = pd.DataFrame(products)
        parquet_path = temp_dir / "test_products.parquet"
        df.to_parquet(parquet_path)
        return parquet_path

    def test_minimum_discount_threshold(self, bronze_products):
        """
        Test that hot-deals have a minimum discount (e.g., 20%+).

        Real hot-deals should have significant savings, not marginal discounts.
        """
        # Read data
        df = pd.read_parquet(bronze_products)

        # Calculate discount percentage
        df["discount_pct"] = ((df["listPrice"] - df["price"]) / df["listPrice"]) * 100

        # Define hot-deal threshold (20% minimum)
        hot_deal_threshold = 20.0

        # Filter hot-deals
        hot_deals = df[df["discount_pct"] >= hot_deal_threshold]

        # Assertions
        assert len(hot_deals) == 3, "Expected 3 products with 20%+ discount"
        assert "1001" in hot_deals["productId"].values, "Arroz (40% off) should be hot-deal"
        assert "1003" in hot_deals["productId"].values, "Óleo (66% off) should be hot-deal"
        assert "1006" in hot_deals["productId"].values, "Leite (25% off) should be hot-deal"
        assert "1002" not in hot_deals["productId"].values, "Feijão (10% off) should NOT be hot-deal"

    def test_price_consistency_validation(self, bronze_products):
        """
        Test that listPrice >= price (basic data quality check).

        Invalid: price > listPrice indicates data corruption or scraping errors.
        """
        df = pd.read_parquet(bronze_products)

        # Find invalid prices
        invalid_prices = df[df["price"] > df["listPrice"]]

        # Assertions
        assert len(invalid_prices) == 1, "Expected 1 product with invalid pricing"
        assert "1004" in invalid_prices["productId"].values, "Açúcar should have invalid pricing"

        # Valid products should have listPrice >= price
        valid_products = df[df["price"] <= df["listPrice"]]
        assert len(valid_products) == 5, "Expected 5 products with valid pricing"

    def test_detect_fake_inflated_deals(self, bronze_products):
        """
        Test detection of suspiciously high discounts (likely fake/inflated).

        Discounts > 70% are suspicious and may indicate:
        - Inflated listPrice (fake anchor pricing)
        - Data scraping errors
        - Clearance/liquidation (legitimate but rare)
        """
        df = pd.read_parquet(bronze_products)

        # Calculate discount percentage
        df["discount_pct"] = ((df["listPrice"] - df["price"]) / df["listPrice"]) * 100

        # Define suspicious threshold (60%+ for testing)
        suspicious_threshold = 60.0

        # Find suspicious deals
        suspicious_deals = df[df["discount_pct"] >= suspicious_threshold]

        # Assertions
        assert len(suspicious_deals) == 1, "Expected 1 suspicious deal"
        assert "1003" in suspicious_deals["productId"].values, "Óleo (66% off) should be flagged as suspicious"

        # Flag for manual review
        for _, product in suspicious_deals.iterrows():
            print(f"⚠️  SUSPICIOUS DEAL: {product['productName']} - {product['discount_pct']:.1f}% off")

    def test_hot_deals_temporal_consistency(self, temp_dir):
        """
        Test that hot-deals persist across multiple scrapes.

        Real promotions should last hours/days, not appear once and disappear.
        Flash deals that appear in only 1 scrape are suspicious.
        """
        # Simulate 3 scrapes over time
        scrape_1 = pd.DataFrame([
            {"productId": "2001", "price": 10.0, "listPrice": 20.0, "scrapedAt": "2026-02-07T08:00:00"},
            {"productId": "2002", "price": 15.0, "listPrice": 25.0, "scrapedAt": "2026-02-07T08:00:00"},
        ])

        scrape_2 = pd.DataFrame([
            {"productId": "2001", "price": 10.0, "listPrice": 20.0, "scrapedAt": "2026-02-07T12:00:00"},
            {"productId": "2002", "price": 14.0, "listPrice": 25.0, "scrapedAt": "2026-02-07T12:00:00"},  # Price changed
            {"productId": "2003", "price": 8.0, "listPrice": 16.0, "scrapedAt": "2026-02-07T12:00:00"},   # New deal
        ])

        scrape_3 = pd.DataFrame([
            {"productId": "2001", "price": 10.0, "listPrice": 20.0, "scrapedAt": "2026-02-07T16:00:00"},
            # 2002 disappeared
            # 2003 disappeared (flash deal - suspicious!)
        ])

        # Combine all scrapes
        all_scrapes = pd.concat([scrape_1, scrape_2, scrape_3], ignore_index=True)

        # Calculate discount
        all_scrapes["discount_pct"] = ((all_scrapes["listPrice"] - all_scrapes["price"]) / all_scrapes["listPrice"]) * 100

        # Find hot-deals (20%+ discount)
        hot_deals = all_scrapes[all_scrapes["discount_pct"] >= 20.0]

        # Count scrapes per product
        scrape_counts = hot_deals.groupby("productId").size()

        # Assertions
        assert scrape_counts["2001"] == 3, "Product 2001 should appear in all 3 scrapes (stable deal)"
        assert scrape_counts["2002"] == 2, "Product 2002 should appear in 2 scrapes"
        assert scrape_counts["2003"] == 1, "Product 2003 is flash deal (appeared once)"

        # Flag flash deals for review
        flash_deals = scrape_counts[scrape_counts == 1]
        assert len(flash_deals) == 1, "Expected 1 flash deal"
        print(f"⚠️  FLASH DEAL (suspicious): {flash_deals.index.tolist()}")

    def test_realistic_discount_distribution(self, bronze_products):
        """
        Test that discount distribution is realistic.

        Most products should have:
        - 0-10% discount (regular pricing)
        - 10-30% discount (common promotions)
        - 30-50% discount (hot-deals)
        - 50%+ discount (rare, suspicious)
        """
        df = pd.read_parquet(bronze_products)

        # Calculate discount
        df["discount_pct"] = ((df["listPrice"] - df["price"]) / df["listPrice"]) * 100

        # Categorize discounts
        df["discount_category"] = pd.cut(
            df["discount_pct"],
            bins=[-float("inf"), 0, 10, 30, 50, float("inf")],
            labels=["Invalid", "Regular", "Modest", "Hot-Deal", "Suspicious"]
        )

        # Count by category
        distribution = df["discount_category"].value_counts()

        # Assertions
        assert distribution["Regular"] >= 1, "Should have some regular-priced products"
        assert distribution["Hot-Deal"] >= 1, "Should have some hot-deals"
        assert distribution.get("Suspicious", 0) <= 2, "Should have few suspicious deals"

        print("\n📊 Discount Distribution:")
        for category in ["Invalid", "Regular", "Modest", "Hot-Deal", "Suspicious"]:
            count = distribution.get(category, 0)
            print(f"  {category}: {count} products")

    def test_hot_deals_quality_score(self, bronze_products):
        """
        Test hot-deals quality scoring.

        Quality factors:
        - Discount range (20-50% = good, >50% = suspicious)
        - Price consistency (valid listPrice > price)
        - Brand reputation (known brands = higher confidence)
        """
        df = pd.read_parquet(bronze_products)

        # Calculate discount
        df["discount_pct"] = ((df["listPrice"] - df["price"]) / df["listPrice"]) * 100

        # Calculate quality score (0-100)
        df["quality_score"] = 0.0

        # Factor 1: Discount in optimal range (20-50%)
        df.loc[(df["discount_pct"] >= 20) & (df["discount_pct"] <= 50), "quality_score"] += 50

        # Factor 2: Valid pricing (listPrice > price)
        df.loc[df["listPrice"] > df["price"], "quality_score"] += 30

        # Factor 3: Brand reputation (simplified: known brands get +20)
        known_brands = ["Tio João", "Camil", "Pilão", "Tirol"]
        df.loc[df["brand"].isin(known_brands), "quality_score"] += 20

        # Filter hot-deals and assess quality
        hot_deals = df[df["discount_pct"] >= 20.0]

        # Assertions
        assert hot_deals["quality_score"].max() == 100, "Should have at least one perfect-score deal"
        assert hot_deals[hot_deals["productId"] == "1001"]["quality_score"].values[0] == 100, \
            "Arroz should have perfect quality score (40% discount, valid price, known brand)"

        print("\n🏆 Hot-Deals Quality Scores:")
        for _, deal in hot_deals.iterrows():
            print(f"  {deal['productName']}: {deal['quality_score']:.0f}/100 ({deal['discount_pct']:.1f}% off)")
