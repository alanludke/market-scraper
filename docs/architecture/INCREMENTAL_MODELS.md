# Incremental Models in DBT - Efficient Data Processing

Incremental models process only *new or changed* data after the initial run. The first `dbt run` processes all rows. Subsequent runs filter and insert/update only specific rows—based on a timestamp, ID, or other logic.

**Why use them for Market Scraper?**

- ✅ **Lower compute cost**: Process only today's scrape, not entire history
- ✅ **Faster execution**: 5 seconds vs 50 seconds for full refresh
- ✅ **Scalability**: Handle growing bronze layer (currently 11GB+)

---

## When to Use

### ✅ Use Incremental for Market Scraper:

- **Bronze → Silver transformation**: Process only new Parquet files from scraper
- **Daily price aggregations**: Calculate metrics for last 24 hours only
- **Historical fact tables**: Append daily snapshots without reprocessing
- **Large datasets**: When `tru_product` exceeds 1M rows

### ❌ Avoid Incremental When:

- **Small dimensions**: `dim_stores` (3 rows), `dim_regions` (37 rows) - just full refresh
- **Full recompute needed**: Metrics that depend on entire history (price percentiles across all time)
- **Dev testing**: Use `--full-refresh` during development to catch bugs

---

## Basic Setup

```sql
-- models/trusted/tru_product.sql
{{ config(
    materialized='incremental',
    unique_key='product_id'
) }}

SELECT
    productId as product_id,
    productName as product_name,
    min_price,
    scraped_at
FROM {{ ref('stg_vtex__products') }}

{% if is_incremental() %}
  -- Only process products scraped after latest in trusted layer
  WHERE scraped_at > (SELECT MAX(scraped_at) FROM {{ this }})
{% endif %}
```

**How it works:**
1. **First run**: Processes all data (full history)
2. **Second run**: Only processes rows where `scraped_at > MAX(scraped_at)`
3. **Daily runs**: Only processes today's scrape (~450K rows, not 10M+)

---

## Incremental Strategies

Set with:

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='merge'  -- or append, delete+insert, insert_overwrite
) }}
```

| Strategy           | Description                                                    | Use When...                                    | DuckDB Support |
| ------------------ | -------------------------------------------------------------- | ---------------------------------------------- | -------------- |
| `append`           | Adds new rows only (no updates)                                | Data is immutable (logs, events)               | ✅ Yes         |
| `merge`            | Matches on `unique_key`, updates if exists, inserts if not     | Records may be updated (price changes)         | ✅ Yes         |
| `delete+insert`    | Deletes matching records, inserts new ones                     | Updates needed, no merge support               | ✅ Yes         |
| `insert_overwrite` | Overwrites partitions (e.g., one day). Requires partition col. | Partitioned data (daily snapshots)             | ❌ No (v1.9)   |

---

## How to Choose Strategy for Market Scraper

### Decision Tree:

```
┌─ Is data append-only (never updated)?
│  ├─ YES → Use `append` (e.g., scraper run logs)
│  └─ NO  → Continue
│
├─ Can same product appear multiple times per day?
│  ├─ YES → Use `merge` with `unique_key=product_id` (deduplicate)
│  └─ NO  → Use `append` (one scrape/day guaranteed unique)
│
└─ Do we partition by date?
   ├─ YES → Use `insert_overwrite` (when DuckDB supports it)
   └─ NO  → Use `merge` or `append`
```

### Recommendation for Market Scraper:

| Model                 | Strategy          | Reason                                                      |
| --------------------- | ----------------- | ----------------------------------------------------------- |
| `tru_product`         | `merge`           | Deduplicates products (same product scraped twice/day)      |
| `fct_prices_daily`    | `append`          | One record per product per day (no updates)                 |
| `fct_price_changes`   | `merge`           | Tracks latest change event                                  |
| `dim_product_history` | `append`          | Append-only audit trail                                     |

---

## Example 1: Merge Strategy (Deduplication)

```sql
-- models/trusted/tru_product.sql
{{ config(
    materialized='incremental',
    unique_key='product_id',  -- Dedup key
    incremental_strategy='merge',
    merge_update_columns=['product_name', 'min_price', 'avg_price', 'is_available', 'scraped_at']
) }}

WITH source_data AS (
    SELECT
        product_id,
        product_name,
        brand,
        min_price,
        avg_price,
        is_available,
        scraped_at,
        ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY scraped_at DESC) as rn
    FROM {{ ref('stg_vtex__products') }}

    {% if is_incremental() %}
      -- Only process new scrapes
      WHERE scraped_at > (SELECT MAX(scraped_at) FROM {{ this }})
    {% endif %}
)

SELECT * EXCLUDE rn
FROM source_data
WHERE rn = 1  -- Keep latest version per product
```

**What happens:**
- If `product_id` exists in `tru_product`: Updates `min_price`, `scraped_at`, etc.
- If `product_id` is new: Inserts new row

---

## Example 2: Append Strategy (Daily Facts)

```sql
-- models/marts/fct_prices_daily.sql
{{ config(
    materialized='incremental',
    incremental_strategy='append'  -- Never update, only add
) }}

SELECT
    product_id,
    supermarket,
    region,
    DATE(scraped_at) as price_date,
    MIN(min_price) as daily_min_price,
    AVG(avg_price) as daily_avg_price,
    MAX(max_price) as daily_max_price,
    COUNT(*) as scrapes_count
FROM {{ ref('tru_product') }}

{% if is_incremental() %}
  -- Only aggregate today's data
  WHERE DATE(scraped_at) > (SELECT MAX(price_date) FROM {{ this }})
{% endif %}

GROUP BY 1, 2, 3, 4
```

**Performance:**
- Full refresh: Aggregates 10M rows → 50 seconds
- Incremental: Aggregates 450K rows (today only) → 5 seconds

---

## Handling Late-Arriving Data

**Problem**: What if yesterday's scrape fails and runs today?

**Solution**: Use lookback window

```sql
{% if is_incremental() %}
  -- Reprocess last 3 days to catch late data
  WHERE DATE(scraped_at) >= CURRENT_DATE - INTERVAL '3 days'
{% endif %}
```

**Trade-off**: Slightly more data processed, but guarantees completeness.

---

## Schema Changes with `on_schema_change`

Controls what happens if columns change in your model:

| Option                  | Behavior                                         | Market Scraper Use Case                    |
| ----------------------- | ------------------------------------------------ | ------------------------------------------ |
| `ignore` (default)      | Ignores new columns; fails on removed ones       | ❌ Breaks if VTEX API adds fields          |
| `fail`                  | Fails the build                                  | ✅ Force explicit schema updates           |
| `append_new_columns`    | Adds new columns to destination table            | ✅ **Recommended**: Auto-adapt to API      |
| `sync_all_columns`      | Syncs new and removed columns (costly)           | ⚠️ Use with caution (data loss possible)   |

**Recommendation:**

```sql
{{ config(
    materialized='incremental',
    on_schema_change='append_new_columns'  -- Auto-add new VTEX fields
) }}
```

---

## Full Refresh Override

Prevent accidental full refreshes on large tables:

```sql
{{ config(
    materialized='incremental',
    full_refresh=false  -- Require explicit --full-refresh --select this_model
) }}
```

**Use case**: Protect `tru_product` (10M rows) from accidental `dbt run --full-refresh`.

**Override when needed:**
```bash
# Force full refresh for specific model only
dbt run --full-refresh --select tru_product
```

---

## Performance Comparison (Market Scraper)

### Scenario: Daily `tru_product` update (450K new rows)

| Approach           | Time | Rows Processed | Cost (AWS EC2) |
| ------------------ | ---- | -------------- | -------------- |
| Full Refresh       | 50s  | 10M            | $0.10/run      |
| Incremental        | 5s   | 450K           | $0.01/run      |
| **Savings**        | 90%  | 95% less       | 90% cheaper    |

### Projected Annual Savings:
- Runs/year: 365
- Full refresh cost: 365 × $0.10 = **$36.50/year**
- Incremental cost: 365 × $0.01 = **$3.65/year**
- **Savings: $32.85/year** (small but scales with more stores)

---

## Best Practices Checklist

✅ **Define logic as full model first** - Test with `materialized='table'` before incremental

✅ **Add `is_incremental()` filter** - Always filter on timestamp or ID

✅ **Use `unique_key` for merge** - Prevents duplicates

✅ **Set `on_schema_change='append_new_columns'`** - Handle VTEX API changes gracefully

✅ **Schedule full refresh weekly** - Catch any incremental drift
   ```bash
   # Sunday 2am: Full refresh
   0 2 * * 0 dbt run --full-refresh --select tru_product
   ```

✅ **Monitor for missing data** - Test freshness:
   ```yaml
   tests:
     - dbt_utils.recency:
         datepart: day
         field: scraped_at
         interval: 2  # Alert if no data in 2 days
   ```

✅ **Use lookback window for critical models** - Catch late-arriving data

✅ **Document incremental logic** - Add comments explaining watermarking logic

---

## Troubleshooting

| Symptom                       | Likely Cause                          | Fix                                           |
| ----------------------------- | ------------------------------------- | --------------------------------------------- |
| Missing recent data           | `is_incremental()` filter too strict  | Add lookback window (3 days)                  |
| Duplicates in incremental run | `unique_key` not set                  | Add `unique_key` config                       |
| Slow incremental builds       | Filter not indexed                    | DuckDB doesn't use indexes; optimize filter   |
| Schema change breaks build    | `on_schema_change='ignore'`           | Change to `append_new_columns`                |
| "Table not found" error       | First run failed                      | Drop table manually: `DROP TABLE tru_product` |

---

## Example: Full Implementation for `tru_product`

```sql
-- models/trusted/tru_product.sql
{{
    config(
        materialized='incremental',
        unique_key='product_id',
        incremental_strategy='merge',
        merge_update_columns=['product_name', 'brand', 'min_price', 'avg_price', 'is_available', 'scraped_at'],
        on_schema_change='append_new_columns',
        full_refresh=false,  -- Require explicit --full-refresh
        contract={
            'enforced': true
        }
    )
}}

WITH source_data AS (
    SELECT
        product_id,
        product_name,
        brand,
        min_price,
        avg_price,
        max_price,
        is_available,
        sku_count,
        eans,
        total_available_quantity,
        scraped_at,
        run_id,
        ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY scraped_at DESC) as rn
    FROM {{ ref('stg_vtex__products') }}

    {% if is_incremental() %}
      -- Incremental: Only process last 3 days (catch late data)
      WHERE DATE(scraped_at) >= CURRENT_DATE - INTERVAL '3 days'
    {% endif %}
),

deduplicated AS (
    SELECT * EXCLUDE rn
    FROM source_data
    WHERE rn = 1
)

SELECT
    product_id,
    product_name,
    brand,
    min_price,
    avg_price,
    max_price,
    is_available,
    sku_count,
    eans,
    total_available_quantity,
    scraped_at,
    run_id,
    CURRENT_TIMESTAMP as loaded_at
FROM deduplicated
```

---

## Next Steps

1. **Convert `tru_product` to incremental** - Apply template above
2. **Monitor first incremental run** - Compare row counts vs full refresh
3. **Schedule weekly full refresh** - Sunday 2am cron job
4. **Measure performance gains** - Log run times before/after
5. **Apply to other large models** - `fct_prices_daily`, `dim_product_history`

---

## References

- [DBT Incremental Models](https://docs.getdbt.com/docs/build/incremental-models)
- [Incremental Strategies](https://docs.getdbt.com/docs/build/incremental-strategy)
- [Schema Evolution](https://docs.getdbt.com/docs/build/incremental-models#what-if-the-columns-of-my-incremental-model-change)
- [Full Refresh Config](https://docs.getdbt.com/reference/resource-configs/full_refresh)
