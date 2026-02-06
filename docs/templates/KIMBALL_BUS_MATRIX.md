# Kimball Bus Matrix Template

## What is a Kimball Bus Matrix?

A **Bus Matrix** is a two-dimensional table that maps:

- **Rows** = Business Processes or Fact Tables (e.g., "Price Tracking", "Inventory", "Sales")
- **Columns** = Conformed Dimensions (e.g., "Date", "Product", "Store", "Region")

Each cell in the matrix indicates whether a given dimension applies to that business process — usually marked with an **X** or checkmark (✅).

**Purpose**: Ensures dimensional consistency across fact tables. Once `dim_product` is defined, **all fact tables use the same definition**.

---

## Market Scraper Bus Matrix (Current State)

| Business Process       | Date | Product | Store | Region | Brand | Category | Time |
| ---------------------- | ---- | ------- | ----- | ------ | ----- | -------- | ---- |
| **Price Tracking**     | ✅   | ✅      | ✅    | ✅     | ✅    | ❌       | ✅   |
| **Availability**       | ✅   | ✅      | ✅    | ✅     | ✅    | ❌       | ✅   |
| **Product Catalog**    | ✅   | ✅      | ✅    | ✅     | ✅    | ❌       | ❌   |
| **Scraper Runs** (Ops) | ✅   | ❌      | ✅    | ✅     | ❌    | ❌       | ✅   |

**Legend**:
- ✅ Dimension applies to this fact
- ❌ Dimension not used

---

## Market Scraper Bus Matrix (Future Roadmap)

| Business Process          | Date | Product | Store | Region | Brand | Category | Promotion | Customer | Time |
| ------------------------- | ---- | ------- | ----- | ------ | ----- | -------- | --------- | -------- | ---- |
| **Price Tracking**        | ✅   | ✅      | ✅    | ✅     | ✅    | ✅       | ✅        | ❌       | ✅   |
| **Availability**          | ✅   | ✅      | ✅    | ✅     | ✅    | ✅       | ❌        | ❌       | ✅   |
| **Product Catalog**       | ✅   | ✅      | ✅    | ✅     | ✅    | ✅       | ❌        | ❌       | ❌   |
| **Sales Transactions**    | ✅   | ✅      | ✅    | ✅     | ✅    | ✅       | ✅        | ✅       | ✅   |
| **Customer Basket**       | ✅   | ✅      | ✅    | ✅     | ✅    | ✅       | ✅        | ✅       | ✅   |
| **Scraper Runs** (Ops)    | ✅   | ❌      | ✅    | ✅     | ❌    | ❌       | ❌        | ❌       | ✅   |
| **Stock Movements**       | ✅   | ✅      | ✅    | ✅     | ✅    | ✅       | ❌        | ❌       | ✅   |

**Future dimensions**:
- **Category** (`dim_category`): Product taxonomy (Alimentos → Grãos → Arroz)
- **Promotion** (`dim_promotion`): Discount campaigns, Black Friday deals
- **Customer** (`dim_customer`): If we add transaction data (receipts, loyalty cards)

---

## How to Build Your Bus Matrix

### Step 1: List Business Processes (Rows)

Identify **fact tables** (business events you want to analyze):

**Market Scraper Examples**:
- Price Tracking (`fct_prices_daily`)
- Availability Tracking (`fct_availability`)
- Product Catalog Snapshot (`fct_product_catalog`)
- Scraper Run Metrics (`fct_scraper_runs`)

**Future Examples**:
- Sales Transactions (`fct_sales`)
- Customer Basket Analysis (`fct_basket`)
- Stock Movements (`fct_inventory`)

### Step 2: Identify Conformed Dimensions (Columns)

List **dimensions shared across multiple facts**:

**Current Dimensions**:
- `dim_date`: Calendar dimension (date, day_of_week, month, year)
- `dim_product`: Product master (product_id, name, brand, EAN)
- `dim_store`: Store master (store_id, name, chain)
- `dim_region`: Geographic regions (region_code, city, postal_code)
- `dim_brand`: Brand master (brand_id, name)
- `dim_time`: Time-of-day dimension (hour, minute, time_bucket)

**Future Dimensions**:
- `dim_category`: Product categories (hierarchy)
- `dim_promotion`: Promotional campaigns
- `dim_customer`: Customer demographics (if transaction data added)

### Step 3: Map Dimensions to Processes

Use ✅ to indicate a process uses a dimension:

**Example**: `fct_prices_daily` uses:
- ✅ Date (price_date)
- ✅ Product (product_id → `dim_product`)
- ✅ Store (supermarket → `dim_store`)
- ✅ Region (region → `dim_region`)
- ✅ Brand (brand → `dim_brand`)

### Step 4: Prioritize for Modeling

**Modeling Priority** (most shared dimensions first):
1. ✅ **`dim_date`** (used by ALL facts) → Build first
2. ✅ **`dim_product`** (used by 4/4 current facts) → Critical
3. ✅ **`dim_store`** (used by 4/4 facts) → Critical
4. ✅ **`dim_region`** (used by 4/4 facts) → Critical
5. ⚠️ **`dim_brand`** (used by 3/4 facts) → Nice to have
6. 🔮 **`dim_category`** (future) → When product hierarchy needed
7. 🔮 **`dim_promotion`** (future) → When tracking deals

---

## Fact Tables Based on Matrix

From the Bus Matrix, define fact tables:

### `fct_prices_daily`
**Grain**: One row per product per store per region per day

**Dimensions**:
- `dim_date` (price_date)
- `dim_product` (product_id)
- `dim_store` (supermarket)
- `dim_region` (region)
- `dim_brand` (brand)

**Measures**:
- `daily_min_price`, `daily_avg_price`, `daily_max_price`, `scrapes_count`

**SQL**:
```sql
SELECT
    dp.product_key,  -- FK to dim_product
    dd.date_key,     -- FK to dim_date
    ds.store_key,    -- FK to dim_store
    dr.region_key,   -- FK to dim_region
    MIN(min_price) as daily_min_price,
    AVG(avg_price) as daily_avg_price,
    MAX(max_price) as daily_max_price,
    COUNT(*) as scrapes_count
FROM {{ ref('tru_product') }} tp
INNER JOIN {{ ref('dim_product') }} dp ON tp.product_id = dp.product_id
INNER JOIN {{ ref('dim_date') }} dd ON DATE(tp.scraped_at) = dd.date
INNER JOIN {{ ref('dim_store') }} ds ON tp.supermarket = ds.store_id
INNER JOIN {{ ref('dim_region') }} dr ON tp.region = dr.region_code
GROUP BY 1, 2, 3, 4
```

### `fct_availability`
**Grain**: One row per product per store per region per hour

**Dimensions**:
- `dim_date` (availability_date)
- `dim_time` (availability_hour)
- `dim_product` (product_id)
- `dim_store` (supermarket)
- `dim_region` (region)

**Measures**:
- `is_available`, `total_quantity`, `out_of_stock_duration_minutes`

### `fct_scraper_runs` (Operational Metrics)
**Grain**: One row per scraper run

**Dimensions**:
- `dim_date` (run_date)
- `dim_time` (run_start_time)
- `dim_store` (supermarket)
- `dim_region` (region)

**Measures**:
- `products_scraped`, `duration_seconds`, `api_calls_count`, `status` (success/failed)

---

## Conformed Dimensions Best Practices

### ✅ DO:
1. **Single Source of Truth**: `dim_product` defined once, used everywhere
2. **Surrogate Keys**: Use auto-increment `product_key` (not natural `product_id`) for FK
3. **Type 2 SCD**: Track dimension changes over time (brand renamed, product reclassified)
4. **Hierarchy**: Support drill-down (Region → City → Store)
5. **Descriptive Attributes**: Include human-readable names (`product_name`, `store_name`)

### ❌ DON'T:
1. **Don't duplicate dimensions**: Each fact should reference **same** `dim_product`
2. **Don't embed attributes in facts**: Move `product_name` to `dim_product`
3. **Don't skip surrogate keys**: Natural keys (EAN, product_id) can change or have collisions
4. **Don't break conformity**: If `dim_store` uses `store_id`, **all facts must too**

---

## Example: Defining `dim_product` (Conformed)

```sql
-- models/conformed/dim_product.sql
{{ config(
    materialized='table',
    schema='conformed'
) }}

WITH products_with_attributes AS (
    SELECT DISTINCT
        product_id,
        product_name,
        brand,
        -- Future: Add category_id, subcategory_id
        MIN(scraped_at) as first_seen_at,
        MAX(scraped_at) as last_seen_at
    FROM {{ ref('tru_product') }}
    GROUP BY 1, 2, 3
)

SELECT
    ROW_NUMBER() OVER (ORDER BY product_id) as product_key,  -- Surrogate key
    product_id,            -- Natural key
    product_name,
    brand,
    first_seen_at,
    last_seen_at,
    CURRENT_TIMESTAMP as loaded_at
FROM products_with_attributes
```

**Usage in Fact**:
```sql
-- Fact table joins on surrogate key (product_key), not natural key
SELECT
    p.product_key,  -- FK to dim_product
    MIN(min_price) as daily_min_price
FROM {{ ref('tru_product') }} t
INNER JOIN {{ ref('dim_product') }} p
    ON t.product_id = p.product_id  -- Join on natural key
GROUP BY 1
```

---

## Validating Your Bus Matrix

### Checklist:
- [ ] All dimensions used by multiple facts are **conformed** (same definition)
- [ ] Surrogate keys (`product_key`) used for FK relationships
- [ ] Fact grain documented (e.g., "one row per product per day")
- [ ] No orphan records (all FKs exist in dimension tables)
- [ ] Dimension tests: `unique`, `not_null` on surrogate keys
- [ ] Relationship tests: `relationships` in fact tables

**DBT Test Example**:
```yaml
# models/marts/fct_prices_daily.yml
models:
  - name: fct_prices_daily
    tests:
      - relationships:
          to: ref('dim_product')
          field: product_key
      - relationships:
          to: ref('dim_date')
          field: date_key
```

---

## Market Scraper Roadmap

### Phase 1 (Current): Basic Dimensions
- ✅ `dim_date`
- ✅ `dim_product` (basic: product_id, name, brand)
- ✅ `dim_store`
- ✅ `dim_region`

### Phase 2 (Next 3 months): Hierarchy
- 🔮 `dim_category` (product taxonomy)
- 🔮 `dim_brand` (standalone dimension with attributes)
- 🔮 `dim_time` (hour-level granularity)

### Phase 3 (6 months): Transactional
- 🔮 `dim_customer` (if adding receipt data)
- 🔮 `dim_promotion` (Black Friday, special offers)
- 🔮 `fct_sales` (actual transaction data)

---

## References

- [Kimball Bus Matrix Guide](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/bus-matrix/)
- [Conformed Dimensions](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/conformed-dimension/)
- [DBT Relationships Tests](https://docs.getdbt.com/reference/resource-properties/tests#relationships)
- [Surrogate Keys in DBT](https://docs.getdbt.com/blog/kimball-dimensional-model)
