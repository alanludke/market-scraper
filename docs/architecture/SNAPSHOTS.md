# Snapshots in DBT - Price History Tracking

## 1. Why Snapshots Matter for Market Scraper

Most scraped data is **mutable**: prices change daily, products go in/out of stock, and availability fluctuates. Without snapshots, we lose historical context. Questions like:

- **"What was the price of Arroz Tio João last month?"**
- **"How long did product X stay out of stock?"**
- **"Which store had the cheapest milk on Black Friday?"**

...require **Slowly Changing Dimension (SCD)** tracking. DBT snapshots make this automatic.

---

## 2. Core Concepts

| Concept   | What it is                                                             | Use Case for Market Scraper       |
| --------- | ---------------------------------------------------------------------- | --------------------------------- |
| **SCD-1** | Overwrites previous value. No history kept.                            | Not useful (loses price history)  |
| **SCD-2** | Inserts new row for every change with valid-from/valid-to timestamps.  | ✅ **Perfect for price tracking** |
| **SCD-3** | Keeps current + previous value in extra columns.                       | Niche; manual implementation      |

Snapshots in DBT implement **SCD-2** out of the box and can record hard deletes (products removed from catalog).

---

## 3. Detecting Row Changes — Snapshot Strategies

### 3.1 Timestamp Strategy *(Recommended for Market Scraper)*

*Detect change when `scraped_at` timestamp advances.*

```yaml
# snapshots/snap_product_prices.yml
snapshots:
  - name: snap_product_prices
    relation: ref('tru_product')
    config:
      schema: snapshots
      unique_key: product_id
      strategy: timestamp
      updated_at: scraped_at  # Our scraper timestamp
      hard_deletes: invalidate
```

**Why use it?**

- ✅ Tracks just **one** column (`scraped_at`) → cheaper queries
- ✅ Survives schema drift (new columns added to `tru_product`)
- ✅ Easy to validate: if `scraped_at` changes, price likely changed

### 3.2 Check Strategy

*Detect change when watched columns differ.*

```yaml
snapshots:
  - name: snap_product_prices_check
    relation: ref('tru_product')
    config:
      schema: snapshots
      unique_key: product_id
      strategy: check
      check_cols: [min_price, avg_price, is_available]
```

Use when:
- ❌ No reliable `scraped_at` timestamp (unlikely for us)
- ⚠️ Heavier: compares multiple columns every run
- ⚠️ Must update `check_cols` when schema changes

---

## 4. How DBT Builds a Snapshot

### First Run
1. Creates `analytics.snapshots.snap_product_prices` table
2. Inserts current data + meta-columns:
   - `dbt_valid_from`: When this price became valid
   - `dbt_valid_to`: When price changed (NULL = current)
   - `dbt_scd_id`: Surrogate key per version
   - `dbt_updated_at`: Value of `scraped_at` used for change detection

### Subsequent Runs
1. Joins new `tru_product` data to existing snapshot on `product_id`
2. If **price changed**:
   - Sets old row's `dbt_valid_to = scraped_at`
   - Inserts new row with `dbt_valid_from = scraped_at`
3. If **unchanged**: Does nothing (efficient!)

---

## 5. Handling Hard Deletes (Products Removed)

Products can disappear from catalogs (discontinued, out of season). Configure `hard_deletes`:

| Value                | Behavior                                                               |
| -------------------- | ---------------------------------------------------------------------- |
| `ignore` (default)   | Deleted products vanish from next run (no history)                     |
| `invalidate`         | Marks last version as closed (`dbt_valid_to = run_timestamp`)          |
| `new_record`         | Inserts new row with `dbt_is_deleted = true` (audit trail preserved)   |

**Recommendation for Market Scraper**: Use `invalidate`

```yaml
config:
  strategy: timestamp
  updated_at: scraped_at
  hard_deletes: invalidate  # Track product removals
```

---

## 6. Configuration Cheatsheet

```yaml
# snapshots/snap_product_prices.yml
snapshots:
  - name: snap_product_prices
    relation: ref('tru_product')
    description: >
      SCD-2 history of product prices across all stores and regions.
      Tracks min_price, avg_price, and availability over time.

    config:
      schema: snapshots
      unique_key: product_id
      strategy: timestamp
      updated_at: scraped_at
      hard_deletes: invalidate
      dbt_valid_to_current: "to_date('9999-12-31')"  # Easier date filtering

      # Optional: Custom meta-column names
      snapshot_meta_column_names:
        dbt_valid_from: price_valid_from
        dbt_valid_to: price_valid_to
```

Place file in `src/transform/dbt_project/snapshots/`.

---

## 7. Best Practices for Market Scraper

1. **Choose rock-solid `unique_key`**: `product_id` works, but consider composite key `product_id || '_' || region` if tracking per-region
2. **Prefer `timestamp` strategy**: Use `scraped_at` (already exists!)
3. **Dedicated schema**: `snapshots` schema separates history from marts
4. **Pre-clean with staging**: Snapshot `tru_product` (already deduplicated) not raw bronze
5. **Schedule daily**: Align with scraper cadence (runs daily at 6am)
6. **Enable tests**:
   ```yaml
   tests:
     - dbt_utils.recency:
         datepart: day
         field: dbt_updated_at
         interval: 2  # Alert if no updates in 2 days
   ```
7. **Set `dbt_valid_to_current = '9999-12-31'`**: Simplifies queries:
   ```sql
   -- Instead of: WHERE dbt_valid_to IS NULL
   -- Use: WHERE dbt_valid_to = '9999-12-31'
   ```
8. **Version snapshots**: If changing strategy, create `snap_product_prices_v2.yml`

---

## 8. Example Queries (After Snapshot)

### Get current prices (latest version)
```sql
SELECT
    product_id,
    product_name,
    min_price,
    is_available
FROM snapshots.snap_product_prices
WHERE dbt_valid_to = '9999-12-31';  -- Current version
```

### Price history for specific product
```sql
SELECT
    product_name,
    min_price,
    dbt_valid_from,
    dbt_valid_to,
    datediff('day', dbt_valid_from, coalesce(dbt_valid_to, current_date)) as days_at_price
FROM snapshots.snap_product_prices
WHERE product_id = '12345'
ORDER BY dbt_valid_from DESC;
```

### Price volatility (how often prices change)
```sql
SELECT
    product_id,
    product_name,
    COUNT(*) - 1 as price_changes_count,
    MIN(min_price) as lowest_price_ever,
    MAX(min_price) as highest_price_ever
FROM snapshots.snap_product_prices
GROUP BY product_id, product_name
HAVING COUNT(*) > 1
ORDER BY price_changes_count DESC;
```

### Products that went out of stock
```sql
SELECT
    product_id,
    product_name,
    dbt_valid_from as out_of_stock_since
FROM snapshots.snap_product_prices
WHERE dbt_valid_to = '9999-12-31'  -- Current version
  AND is_available = false;
```

---

## 9. Troubleshooting

| Symptom                            | Likely Cause                            | Fix                                      |
| ---------------------------------- | --------------------------------------- | ---------------------------------------- |
| Duplicate `product_id` in snapshot | Source `tru_product` has duplicates     | Fix deduplication in `tru_product` model |
| Snapshot very slow                 | Using `check` on many columns           | Switch to `timestamp` strategy           |
| Deletes not captured               | `hard_deletes: ignore`                  | Change to `invalidate` or `new_record`   |
| Too many versions created          | `scraped_at` updates even if no change  | Filter unchanged rows in staging         |

---

## 10. Running Snapshots

```bash
# Run all snapshots
cd src/transform/dbt_project
dbt snapshot

# Run specific snapshot
dbt snapshot --select snap_product_prices

# Check snapshot freshness
dbt source freshness
```

**Orchestration**: Schedule `dbt snapshot` daily **after** scraper runs (e.g., 7:00am if scraper runs at 6:00am).

---

## 11. Market Scraper Use Cases

### Use Case 1: Price Trend Dashboard
Show how Arroz Tio João price evolved across stores over 30 days.

### Use Case 2: Competitiveness Alerts
Detect when Fort's average price drops below Bistek's (competitor undercut).

### Use Case 3: Seasonal Analysis
Identify products with cyclical pricing (e.g., beer prices spike during summer).

### Use Case 4: Audit Trail
Regulatory compliance: prove pricing data for specific dates (e.g., Black Friday claims).

### Use Case 5: ML Training Data
Feed historical prices to ML models for demand forecasting.

---

## 12. Meta-Columns Reference

| Column               | Meaning                                          | Example                      |
| -------------------- | ------------------------------------------------ | ---------------------------- |
| `dbt_valid_from`     | When this price became valid                     | `2026-02-01 06:15:00`        |
| `dbt_valid_to`       | When price changed (9999-12-31 = current)        | `2026-02-05 06:10:00`        |
| `dbt_scd_id`         | Surrogate key per version                        | `abc123def456` (hash)        |
| `dbt_updated_at`     | Value of `scraped_at` used for change detection  | `2026-02-05 06:10:00`        |
| `dbt_is_deleted`     | True/False (when `hard_deletes = 'new_record'`)  | `false`                      |

---

## 13. Final Thoughts

Snapshots unlock **temporal analytics** for market_scraper:

- ✅ Track price changes over time (no data loss)
- ✅ Answer "point-in-time" questions (what was price on date X?)
- ✅ Audit trail for compliance
- ✅ ML-ready historical dataset
- ✅ Zero changes to source scrapers (just DBT config)

**Next Steps**:
1. Create `snapshots/snap_product_prices.yml`
2. Run `dbt snapshot` after next scraper run
3. Build price history dashboard in Streamlit
4. Set up alerts for anomalous price changes

---

## References

- [DBT Snapshots Documentation](https://docs.getdbt.com/docs/build/snapshots)
- [Snapshot Strategy Guide](https://docs.getdbt.com/reference/resource-configs/strategy)
- [SCD Type 2 Best Practices](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-2/)
