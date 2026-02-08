"""
CLI tool to validate hot-deals quality in scraped data.

Usage:
    python scripts/validate_hot_deals_quality.py --store bistek --min-discount 20
    python scripts/validate_hot_deals_quality.py --all --output report.json
"""

import argparse
import json
from pathlib import Path
import pandas as pd
import sys
from datetime import datetime


def validate_hot_deals(
    store: str = None,
    min_discount: float = 20.0,
    max_discount: float = 70.0,
    output: str = None
):
    """
    Validate hot-deals quality in bronze layer data.

    Args:
        store: Store name (e.g., 'bistek') or None for all stores
        min_discount: Minimum discount percentage for hot-deals
        max_discount: Maximum discount before flagging as suspicious
        output: Output file path for JSON report
    """
    print(f"🔍 Validating hot-deals (discount: {min_discount}%-{max_discount}%)...")

    # Find parquet files
    bronze_dir = Path("data/bronze")
    if not bronze_dir.exists():
        print("❌ No bronze data found")
        return

    # Pattern for store filtering
    if store:
        pattern = f"supermarket={store}/**/*.parquet"
    else:
        pattern = "**/*.parquet"

    parquet_files = list(bronze_dir.glob(pattern))
    if not parquet_files:
        print(f"❌ No parquet files found for pattern: {pattern}")
        return

    print(f"📂 Found {len(parquet_files)} parquet files\n")

    # Read all data
    dfs = []
    for file in parquet_files:
        try:
            df = pd.read_parquet(file)
            # Extract store from path
            store_name = str(file).split("supermarket=")[1].split("/")[0] if "supermarket=" in str(file) else "unknown"
            df["store"] = store_name
            dfs.append(df)
        except Exception as e:
            print(f"⚠️  Failed to read {file}: {e}")

    if not dfs:
        print("❌ No data loaded")
        return

    # Combine all data
    df = pd.concat(dfs, ignore_index=True)
    print(f"📊 Total products: {len(df):,}")

    # Filter only products with both price and listPrice
    df_with_prices = df.dropna(subset=["price", "listPrice"])
    print(f"📊 Products with pricing: {len(df_with_prices):,}")

    # Calculate discount percentage
    df_with_prices["discount_pct"] = (
        (df_with_prices["listPrice"] - df_with_prices["price"]) / df_with_prices["listPrice"]
    ) * 100

    # === DATA QUALITY CHECKS ===
    print("\n" + "=" * 60)
    print("📋 DATA QUALITY CHECKS")
    print("=" * 60)

    # Check 1: Invalid pricing (price > listPrice)
    invalid_pricing = df_with_prices[df_with_prices["price"] > df_with_prices["listPrice"]]
    print(f"❌ Invalid pricing (price > listPrice): {len(invalid_pricing):,} products")
    if len(invalid_pricing) > 0:
        print(f"   Top offenders:")
        for _, row in invalid_pricing.head(5).iterrows():
            print(f"   - {row['productName'][:50]}: price={row['price']:.2f} > listPrice={row['listPrice']:.2f}")

    # Check 2: No discount (price == listPrice)
    no_discount = df_with_prices[df_with_prices["price"] == df_with_prices["listPrice"]]
    print(f"ℹ️  No discount: {len(no_discount):,} products ({len(no_discount)/len(df_with_prices)*100:.1f}%)")

    # === HOT-DEALS ANALYSIS ===
    print("\n" + "=" * 60)
    print(f"🔥 HOT-DEALS ANALYSIS (discount >= {min_discount}%)")
    print("=" * 60)

    # Filter hot-deals
    hot_deals = df_with_prices[df_with_prices["discount_pct"] >= min_discount]
    print(f"✅ Total hot-deals: {len(hot_deals):,} ({len(hot_deals)/len(df_with_prices)*100:.1f}%)")

    if len(hot_deals) == 0:
        print("   No hot-deals found!")
        return

    # Statistics
    print(f"📊 Average discount: {hot_deals['discount_pct'].mean():.1f}%")
    print(f"📊 Median discount: {hot_deals['discount_pct'].median():.1f}%")
    print(f"📊 Max discount: {hot_deals['discount_pct'].max():.1f}%")

    # Distribution
    print("\n📊 Discount Distribution:")
    bins = [min_discount, 30, 50, max_discount, float("inf")]
    labels = [f"{min_discount}-30%", "30-50%", f"50-{max_discount}%", f"{max_discount}%+"]
    hot_deals["discount_category"] = pd.cut(hot_deals["discount_pct"], bins=bins, labels=labels)
    for category in labels:
        count = (hot_deals["discount_category"] == category).sum()
        pct = (count / len(hot_deals)) * 100
        print(f"   {category}: {count:,} deals ({pct:.1f}%)")

    # === SUSPICIOUS DEALS ===
    print("\n" + "=" * 60)
    print(f"⚠️  SUSPICIOUS DEALS (discount > {max_discount}%)")
    print("=" * 60)

    suspicious_deals = hot_deals[hot_deals["discount_pct"] > max_discount]
    print(f"🚨 Total suspicious: {len(suspicious_deals):,}")

    if len(suspicious_deals) > 0:
        print("\n   Top 10 most suspicious:")
        top_suspicious = suspicious_deals.nlargest(10, "discount_pct")
        for idx, row in top_suspicious.iterrows():
            print(f"   - {row['productName'][:50]}")
            print(f"     {row['discount_pct']:.1f}% off | price={row['price']:.2f} | listPrice={row['listPrice']:.2f} | store={row['store']}")

    # === TOP HOT-DEALS ===
    print("\n" + "=" * 60)
    print(f"🏆 TOP 10 HOT-DEALS (best legitimate deals)")
    print("=" * 60)

    # Filter legitimate deals (discount between min and max)
    legitimate_deals = hot_deals[
        (hot_deals["discount_pct"] >= min_discount) &
        (hot_deals["discount_pct"] <= max_discount)
    ]

    if len(legitimate_deals) > 0:
        top_deals = legitimate_deals.nlargest(10, "discount_pct")
        for idx, row in top_deals.iterrows():
            print(f"   {idx+1}. {row['productName'][:60]}")
            print(f"      {row['discount_pct']:.1f}% off | R$ {row['price']:.2f} (was R$ {row['listPrice']:.2f})")
            print(f"      Store: {row['store']} | Brand: {row.get('brand', 'N/A')}\n")
    else:
        print("   No legitimate hot-deals found!")

    # === BY STORE ===
    print("\n" + "=" * 60)
    print("🏪 HOT-DEALS BY STORE")
    print("=" * 60)

    store_stats = hot_deals.groupby("store").agg({
        "productId": "count",
        "discount_pct": ["mean", "max"]
    }).round(1)
    store_stats.columns = ["count", "avg_discount", "max_discount"]
    store_stats = store_stats.sort_values("count", ascending=False)

    for store_name, stats in store_stats.iterrows():
        print(f"   {store_name}: {int(stats['count'])} deals | avg {stats['avg_discount']:.1f}% | max {stats['max_discount']:.1f}%")

    # === GENERATE REPORT ===
    if output:
        report = {
            "generated_at": datetime.now().isoformat(),
            "parameters": {
                "store": store,
                "min_discount": min_discount,
                "max_discount": max_discount,
            },
            "summary": {
                "total_products": int(len(df)),
                "products_with_pricing": int(len(df_with_prices)),
                "total_hot_deals": int(len(hot_deals)),
                "hot_deals_percentage": float(len(hot_deals) / len(df_with_prices) * 100),
                "average_discount": float(hot_deals["discount_pct"].mean()),
                "median_discount": float(hot_deals["discount_pct"].median()),
                "max_discount": float(hot_deals["discount_pct"].max()),
            },
            "quality": {
                "invalid_pricing_count": int(len(invalid_pricing)),
                "suspicious_deals_count": int(len(suspicious_deals)),
            },
            "by_store": store_stats.to_dict(),
        }

        with open(output, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n✅ Report saved to: {output}")


def main():
    parser = argparse.ArgumentParser(description="Validate hot-deals quality")
    parser.add_argument("--store", help="Store name (e.g., bistek)")
    parser.add_argument("--all", action="store_true", help="Analyze all stores")
    parser.add_argument("--min-discount", type=float, default=20.0, help="Minimum discount %% (default: 20)")
    parser.add_argument("--max-discount", type=float, default=70.0, help="Maximum legitimate discount %% (default: 70)")
    parser.add_argument("--output", help="Output JSON report file")

    args = parser.parse_args()

    if not args.all and not args.store:
        parser.print_help()
        sys.exit(1)

    validate_hot_deals(
        store=args.store,
        min_discount=args.min_discount,
        max_discount=args.max_discount,
        output=args.output,
    )


if __name__ == "__main__":
    main()
