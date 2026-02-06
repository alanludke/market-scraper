# Data Layers - Medallion Architecture

This document describes the layered data architecture used in the Market Scraper platform, following the **Medallion Architecture** pattern with DBT transformations.

## Overview

The platform uses a 5-layer architecture that progressively transforms raw data into consumption-ready analytics:

```
Raw (Bronze) → Staging (Silver) → Trusted → Marts (Gold) → Serving
```

Each layer has specific responsibilities, naming conventions, and metadata requirements.

---

## Layer Structure Summary

| Layer | Purpose | Operations | Materialization | Naming Pattern |
|-------|---------|------------|-----------------|----------------|
| **Raw** | Landing zone from APIs | None (external tables) | External Parquet | `bronze_{source}/{table}` |
| **Staging** | Pre-processing, standardization | Cast, rename, basic cleaning | Ephemeral | `stg_{source}__{entity}` |
| **Trusted** | Entity-driven conformed data | Joins, unions, deduplication | Table/Incremental | `tru_{entity}` |
| **Marts** | Business logic, analytics-ready | Aggregations, KPIs, dimensions | Table/Incremental | `fct_{process}`, `dim_{entity}` |
| **Serving** | Flattened wide tables for BI | Combine facts+dimensions | Table/Incremental | `obt_{entity}__{purpose}` |

---

## 1. Raw Layer (Bronze)

### Definition
Landing zone of source data from VTEX API. Data is stored as-is in Parquet format without transformations.

### Location
- **Path**: `data/bronze/supermarket={store}/region={region}/year={yyyy}/month={mm}/day={dd}/run_{timestamp}.parquet`
- **DBT**: Defined as external sources in `models/staging/sources.yml`

### Characteristics
- ✅ **No transformations** - Exact copy of API response
- ✅ **Partitioned** - By supermarket, region, date
- ✅ **Compressed** - Snappy compression (Parquet)
- ✅ **Immutable** - Never modified after writing

### Metadata Columns
| Column | Type | Description |
|--------|------|-------------|
| `_metadata_scraped_at` | timestamp | When data was extracted from API |
| `_metadata_supermarket` | string | Source store (bistek, fort, giassi) |
| `_metadata_region` | string | Region identifier |
| `_metadata_run_id` | string | Scraper execution ID for traceability |

### YAML Metadata
```yaml
meta:
  contains_pii: false
  source_system: vtex
  source_owner: Analytics Team
  source_contact_email: analytics@team.com
  load_frequency: daily
```

### Market Scraper Example
```yaml
# models/staging/sources.yml
sources:
  - name: bronze_bistek
    meta:
      source_system: vtex
      load_frequency: daily
    tables:
      - name: products
        external:
          location: '../../../../data/bronze/supermarket=bistek/**/*.parquet'
```

---

## 2. Staging Layer (Silver - Ephemeral)

### Definition
Foundation layer for pre-processing, casting, and standardization. **Ephemeral** (not materialized as tables).

### Purpose
- Cast data types explicitly
- Rename columns to standard naming
- Basic deduplication
- Simple computations
- Categorize values

### Operations (What to DO)
✅ **DO**:
- Cast types: `cast(id as string)`
- Rename: `productId → product_id`
- Basic cleaning: `trim(name)`, `lower(email)`
- Add system context: `'vtex' as system_name`
- Filter obvious junk: `where product_id is not null`

❌ **DON'T**:
- No joins between sources
- No business logic
- No aggregations
- No complex transformations

### Naming Convention
```
stg_{source}__{entity}
```

**Examples**:
- ✅ `stg_vtex__products`
- ✅ `stg_bistek__products`
- ❌ `stg_vtex_products` (missing double underscore)
- ❌ `staging_products` (wrong prefix)

### Materialization
```yaml
# dbt_project.yml
models:
  staging:
    +materialized: ephemeral
    +schema: staging
```

### Metadata Columns
| Column | Type | Description |
|--------|------|-------------|
| `extract_at` | timestamp | When extracted (from raw) |
| `updated_at` | timestamp | Last modified in source |
| `system_name` | string | Source system identifier |

### YAML Metadata
```yaml
meta:
  graining: product_per_region
  contains_pii: false
  source_system: vtex
  ingestion_type: full_load
  load_frequency: daily
```

### Market Scraper Example
```sql
-- models/staging/stg_vtex__products.sql
with
    source_products as (
        select * from {{ source('bronze_bistek', 'products') }}
    ),

    renamed as (
        select
            cast(productId as string) as product_id,
            cast(productName as string) as product_name,
            cast(brand as string) as brand,
            cast(_metadata_supermarket as string) as supermarket,
            cast(_metadata_region as string) as region,
            cast(_metadata_scraped_at as timestamp) as extract_at,
            'vtex' as system_name
        from source_products
        where productId is not null
    )

select * from renamed
```

---

## 3. Trusted Layer

### Definition
Entity-driven conformed layer where sources are unified and standardized. **No business rules yet** - focus on entity integrity.

### Purpose
- Conform multiple sources into single entities
- Standardize common fields across sources
- Union similar tables
- Translate null values
- Deduplicate records
- Maintain entity history

### Operations (What to DO)
✅ **DO**:
- Union sources: `bistek UNION fort UNION giassi`
- Deduplicate: `qualify row_number() ... = 1`
- Standardize: Common field names, value mappings
- Join for enrichment: Add reference data
- Flatten nested structures: `unnest(items)`

❌ **DON'T**:
- No business KPIs yet
- No aggregations
- No complex calculations
- Keep it entity-focused

### Naming Convention
```
tru_{entity}
```

**Examples**:
- ✅ `tru_product`
- ✅ `tru_price`
- ✅ `tru_customer`
- ❌ `trusted_product`
- ❌ `products`

### Materialization
```yaml
# dbt_project.yml
models:
  trusted:
    +materialized: table
    +schema: trusted
    +contract:
      enforced: true
```

### Metadata Columns
| Column | Type | Description |
|--------|------|-------------|
| `system_name` | string | Source system (when relevant for multi-source) |
| `extract_at` | timestamp | When extracted from source |
| `updated_at` | timestamp | Last modification in source |
| `loaded_at` | timestamp | When loaded into trusted layer |

### YAML Metadata
```yaml
meta:
  graining: product_per_region_per_day
  contains_pii: false
  table_owner: Analytics Team
  area_owner: Pricing Analytics
  owner_email: analytics@team.com
  model_maturity: high
  access_type: public
  load_frequency: daily
```

### Market Scraper Example
```sql
-- models/trusted/tru_product.sql
{{
    config(
        materialized='table',
        contract={'enforced': true}
    )
}}

with
    staging_products as (
        select * from {{ ref('stg_vtex__products') }}
    ),

    deduplicated as (
        select * from staging_products
        qualify row_number() over (
            partition by product_id, region, cast(extract_at as date)
            order by extract_at desc
        ) = 1
    ),

    add_audit as (
        select
            *,
            current_timestamp() as loaded_at
        from deduplicated
    )

select * from add_audit
```

---

## 4. Marts Layer (Gold)

### Definition
Business logic layer with consumption-ready, analytics-optimized data. Implements dimensional modeling (facts & dimensions).

### Purpose
- Apply business rules
- Calculate KPIs and metrics
- Create surrogate keys
- Build fact and dimension tables
- Aggregate for performance

### Operations (What to DO)
✅ **DO**:
- Business calculations: `revenue = quantity * price`
- Aggregations: `sum()`, `avg()`, `count()`
- Create dimensions: Slowly Changing Dimensions (SCD Type 2)
- Create facts: Transactional or aggregated
- Generate surrogate keys: `{{ dbt_utils.generate_surrogate_key(['col1', 'col2']) }}`

### Naming Convention

**Facts** (transactional or aggregate data):
```
fct_{business_process}
fct_{business_process}_{grain}
```

**Dimensions** (descriptive attributes):
```
dim_{entity}
```

**Examples**:
- ✅ `fct_prices_daily`
- ✅ `fct_sales_orders`
- ✅ `dim_products`
- ✅ `dim_stores`
- ❌ `fact_prices` (use full word)
- ❌ `products_dim` (wrong order)

### Materialization
```yaml
# dbt_project.yml
models:
  marts:
    +materialized: table  # or incremental for large tables
    +schema: pricing_marts  # or sales_marts, etc.
    +contract:
      enforced: true
```

### Metadata Columns
| Column | Type | Description |
|--------|------|-------------|
| `loaded_at` | timestamp | When record was loaded into mart |
| `updated_at` | timestamp | Last modification timestamp |

### YAML Metadata
```yaml
meta:
  graining: product_store_day
  contains_pii: false
  area_owner: Pricing Analytics
  owner_email: pricing@team.com
  model_maturity: high
  access_type: public
  load_frequency: daily
  main_kpis: avg_price, price_variance, min_price, max_price
  product_usage: Price Dashboard, Competitive Analysis, API
```

### Market Scraper Example

**Dimension:**
```sql
-- models/marts/dim_products.sql
{{ config(materialized='table', schema='pricing_marts') }}

with
    products as (
        select * from {{ ref('tru_product') }}
    ),

    add_keys as (
        select
            {{ dbt_utils.generate_surrogate_key(['product_id', 'supermarket']) }} as product_sk,
            product_id,
            product_name,
            brand,
            supermarket,
            sku_count,
            is_available,
            loaded_at,
            current_timestamp() as updated_at
        from products
    )

select * from add_keys
```

**Fact:**
```sql
-- models/marts/fct_prices_daily.sql
{{ config(materialized='incremental', schema='pricing_marts') }}

with
    products as (
        select * from {{ ref('tru_product') }}
    ),

    daily_prices as (
        select
            product_id,
            supermarket,
            region,
            cast(scraped_date as date) as price_date,
            min_price,
            avg_price,
            max_price,
            is_available,
            current_timestamp() as loaded_at
        from products
        group by 1, 2, 3, 4, 8
    )

select * from daily_prices

{% if is_incremental() %}
where price_date > (select max(price_date) from {{ this }})
{% endif %}
```

---

## 5. Serving Layer (Optional)

### Definition
Flattened wide tables combining facts and dimensions, optimized for specific BI tools or reports.

### Purpose
- Combine fact + dimension tables (denormalized)
- Apply fixed filters for specific use cases
- Adjust granularity for dashboards
- Add business-friendly flags and labels
- Rename columns to business terminology

### Operations (What to DO)
✅ **DO**:
- Join facts with dimensions: Denormalize star schema
- Add computed flags: `is_expensive`, `price_category`
- Rename for business: `product_name → "Product Name"`
- Pre-filter: Only active products, last 90 days
- Adjust grain: Daily → Weekly if needed

### Naming Convention
```
obt_{entity}__{purpose}
```

**Examples**:
- ✅ `obt_price_competitiveness_report`
- ✅ `obt_product_catalog__dashboard`
- ✅ `obt_sales_executive_summary`
- ❌ `dash_price_report` (wrong prefix)
- ❌ `price_dashboard` (missing obt_)

### Materialization
```yaml
# dbt_project.yml
models:
  serving:
    +materialized: table
    +schema: serving
```

### YAML Metadata
```yaml
meta:
  graining: product_store_day
  contains_pii: false
  table_owner: Analytics Team
  area_owner: Pricing Analytics
  owner_email: analytics@team.com
  model_maturity: high
  access_type: public
  main_kpis: price_index, competitiveness_score
  product_usage: Pricing Dashboard (Streamlit), Weekly Report (Excel)
  load_frequency: daily
```

### Market Scraper Example
```sql
-- models/serving/obt_price_competitiveness_report.sql
{{ config(materialized='table', schema='serving') }}

with
    prices as (
        select * from {{ ref('fct_prices_daily') }}
    ),

    products as (
        select * from {{ ref('dim_products') }}
    ),

    stores as (
        select * from {{ ref('dim_stores') }}
    ),

    joined as (
        select
            products.product_name as "Product Name",
            products.brand as "Brand",
            stores.store_name as "Supermarket",
            stores.region_name as "Region",
            prices.price_date as "Date",
            prices.min_price as "Price (USD)",
            prices.is_available as "In Stock",

            -- Computed flags for dashboard
            case
                when prices.min_price < 5 then 'Budget'
                when prices.min_price < 20 then 'Mid-Range'
                else 'Premium'
            end as "Price Category"

        from prices
        inner join products on prices.product_id = products.product_id
        inner join stores on prices.supermarket = stores.store_id
        where prices.price_date >= current_date - interval 90 days
    )

select * from joined
```

---

## Metadata Structure

### Column Metadata (Physical Columns)

These columns should exist in your tables:

| Column | Layers | Type | Required | Description |
|--------|--------|------|----------|-------------|
| `extract_at` | Raw, Staging, Trusted | timestamp | ✅ | When data was extracted from API |
| `updated_at` | Raw, Staging, Trusted, Marts, Serving | timestamp | ✅ | Last modification in source |
| `loaded_at` | Trusted, Marts, Serving | timestamp | ✅ | When loaded into this layer |
| `system_name` | Staging, Trusted | string | ⚠️ | Source system (for multi-source entities) |

### YAML Metadata (Documentation)

These fields should be in your `schema.yml` files:

| Field | Layers | Required | Values | Description |
|-------|--------|----------|--------|-------------|
| `graining` | All | ✅ | `transaction`, `aggregated`, `product_per_day` | Granularity of data |
| `contains_pii` | All | ✅ | `true`, `false` | Has personal identifiable info? |
| `source_system` | Raw, Staging | ✅ | `vtex`, `sap`, etc. | Original system |
| `table_owner` | Trusted, Marts, Serving | ✅ | Team/person name | Who maintains this |
| `area_owner` | Trusted, Marts, Serving | ✅ | Business area | Which department owns |
| `owner_email` | Trusted, Marts, Serving | ✅ | Email | Contact for questions |
| `model_maturity` | Trusted, Marts, Serving | ✅ | `low`, `mid`, `high` | Production readiness |
| `access_type` | Trusted, Marts, Serving | ✅ | `public`, `restricted` | Who can access |
| `load_frequency` | All | ✅ | `hourly`, `daily`, `weekly` | Refresh cadence |
| `main_kpis` | Marts, Serving | ⚠️ | Comma-separated list | Key metrics |
| `product_usage` | Marts, Serving | ⚠️ | Comma-separated list | Where it's used |

---

## Best Practices

### 1. Keep Layers Focused
- **Staging**: Only standardization, no business logic
- **Trusted**: Entity integrity, no KPIs
- **Marts**: Business logic, analytics-ready

### 2. Use Contracts
```yaml
config:
  contract:
    enforced: true
```
Enforce schema contracts in Trusted and Marts to prevent breaking changes.

### 3. Incremental Processing
For large tables, use incremental materialization:
```sql
{{ config(materialized='incremental') }}

{% if is_incremental() %}
where updated_at > (select max(updated_at) from {{ this }})
{% endif %}
```

### 4. Document Everything
Every model must have:
- Model description
- Column descriptions
- Meta tags (graining, owner, KPIs)
- Data tests (primary keys, relationships)

### 5. Test Primary Keys
```yaml
columns:
  - name: product_id
    data_tests:
      - unique
      - not_null
```

---

## Market Scraper Layer Implementation

| Layer | Status | Models |
|-------|--------|--------|
| Raw (Bronze) | ✅ Complete | External Parquet files |
| Staging | ✅ Complete | `stg_vtex__products` |
| Trusted | 🚧 In Progress | `tru_product` ✅, `tru_price` ⏳ |
| Marts | ⏳ Planned | `fct_prices_daily`, `dim_products`, `dim_stores` |
| Serving | ⏳ Planned | `obt_price_competitiveness_report` |

---

## References

- [DBT Best Practices](https://docs.getdbt.com/best-practices)
- [Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture)
- [Dimensional Modeling (Kimball)](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/)
