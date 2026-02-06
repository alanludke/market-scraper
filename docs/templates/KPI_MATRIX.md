# KPI Matrix Template

Use this template to document key performance indicators (KPIs) and their implementation in DBT models.

---

## KPI Definition Template

| KPI Name | Definition | Business Question | Formula | Source Tables | Owner |
|----------|------------|-------------------|---------|---------------|-------|
| Average Price by Region | Mean product price per region | Which regions are most expensive? | `AVG(min_price) GROUP BY region` | `tru_product` | Pricing Team |
| Price Variance | Price volatility per product | Which products have unstable pricing? | `STDDEV(price) / AVG(price)` | `fct_prices_daily` | Analytics |

---

## Market Scraper KPI Matrix

### Pricing KPIs

| KPI | Definition | Formula | Model | Refresh |
|-----|------------|---------|-------|---------|
| **Average Price by Store** | Mean price across all products per store | `AVG(min_price) GROUP BY supermarket` | `fct_prices_daily` | Daily |
| **Lowest Price Store** | Store with cheapest avg prices | `MIN(avg_price) GROUP BY product_id` | `fct_prices_daily` | Daily |
| **Price Volatility** | Standard deviation of prices | `STDDEV(min_price) / AVG(min_price)` | `fct_prices_daily` | Daily |
| **Competitiveness Score** | Rank of store prices (1=cheapest) | `RANK() OVER (PARTITION BY product_id ORDER BY price)` | `fct_prices_daily` | Daily |

### Catalog KPIs

| KPI | Definition | Formula | Model | Refresh |
|-----|------------|---------|-------|---------|
| **Product Catalog Size** | Total unique products per store | `COUNT(DISTINCT product_id) GROUP BY supermarket` | `tru_product` | Daily |
| **Availability Rate** | % of products in stock | `SUM(is_available) / COUNT(*) * 100` | `tru_product` | Daily |
| **SKU Count per Product** | Avg variants per product | `AVG(sku_count) GROUP BY supermarket` | `tru_product` | Daily |

### Operational KPIs

| KPI | Definition | Formula | Model | Refresh |
|-----|------------|---------|-------|---------|
| **Data Freshness** | Hours since last scrape | `(NOW() - MAX(scraped_at)) / 3600` | `runs` (metrics) | Real-time |
| **Scrape Success Rate** | % of successful scrapes | `SUM(status='success') / COUNT(*) * 100` | `runs` | Daily |
| **Products Scraped per Day** | Total products collected | `SUM(products_scraped) GROUP BY date` | `runs` | Daily |

---

## Implementation Checklist

For each KPI:

- [ ] **Define clearly** - Business question + formula
- [ ] **Identify sources** - Which tables/models provide data
- [ ] **Create DBT model** - Materialized table with KPI
- [ ] **Add tests** - Validate ranges, nulls, logic
- [ ] **Document** - Add to `schema.yml` with `main_kpis` meta tag
- [ ] **Visualize** - Dashboard or report showing KPI
- [ ] **Set alerts** - Thresholds for anomalies

---

## Example: Implementing a New KPI

### KPI: "Most Competitive Products"

**Definition**: Products where a store offers the lowest price vs competitors.

**Business Question**: Which products should we highlight in marketing?

**Formula**:
```sql
WITH ranked_prices AS (
    SELECT
        product_id,
        supermarket,
        min_price,
        RANK() OVER (PARTITION BY product_id ORDER BY min_price) as price_rank
    FROM fct_prices_daily
    WHERE price_date = CURRENT_DATE
)
SELECT
    supermarket,
    COUNT(*) as competitive_products_count
FROM ranked_prices
WHERE price_rank = 1  -- Cheapest
GROUP BY supermarket
```

**Implementation**:
```sql
-- models/marts/fct_competitive_products.sql
{{ config(materialized='table', schema='pricing_marts') }}

WITH ranked_prices AS (
    SELECT
        product_id,
        product_name,
        supermarket,
        min_price,
        RANK() OVER (PARTITION BY product_id ORDER BY min_price) as price_rank
    FROM {{ ref('fct_prices_daily') }}
    INNER JOIN {{ ref('dim_products') }} USING (product_id)
    WHERE price_date = CURRENT_DATE
)

SELECT * FROM ranked_prices WHERE price_rank = 1
```

**Documentation**:
```yaml
# schema.yml
models:
  - name: fct_competitive_products
    description: Products where store has lowest price vs competitors
    config:
      meta:
        main_kpis: competitive_products_count
        product_usage: Marketing Dashboard, Price Alerts
```

---

## KPI Dashboard Layout

Suggested Streamlit dashboard structure:

```python
# dashboards/kpi_dashboard.py
import streamlit as st
import duckdb

st.title("Market Scraper KPIs")

# Pricing KPIs
st.header("Pricing")
col1, col2, col3 = st.columns(3)
col1.metric("Avg Price (Bistek)", "$12.50", "+$0.30")
col2.metric("Avg Price (Fort)", "$11.80", "-$0.20")
col3.metric("Avg Price (Giassi)", "$12.10", "+$0.10")

# Catalog KPIs
st.header("Catalog")
col1, col2 = st.columns(2)
col1.metric("Total Products", "30,450", "+120")
col2.metric("Availability Rate", "94.2%", "+1.3%")

# Operational KPIs
st.header("Operations")
col1, col2, col3 = st.columns(3)
col1.metric("Data Freshness", "2.5 hours", "🟢")
col2.metric("Success Rate", "98.5%", "🟢")
col3.metric("Daily Scrapes", "450K rows", "🟢")
```

---

## Resources

- [Kimball KPI Best Practices](https://www.kimballgroup.com/)
- [DBT Metrics](https://docs.getdbt.com/docs/build/metrics)
- [Streamlit Metrics](https://docs.streamlit.io/library/api-reference/data/st.metric)
