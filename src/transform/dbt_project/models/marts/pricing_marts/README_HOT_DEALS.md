# Hot-Deals Validation Models

## Overview

This directory contains DBT models for validating and analyzing hot-deals (promotional discounts) scraped from supermarket websites.

**Purpose**: Ensure hot-deals are **real, legitimate promotions** and filter out fake/suspicious deals caused by:
- Inflated anchor pricing (fake "was $X, now $Y")
- Data scraping errors
- Flash deals that appear briefly (may be errors)
- Pricing inconsistencies

---

## Models

### 📊 `fct_hot_deals_validated` (Fact Table)

**Description**: Validated hot-deals with quality scoring and legitimacy classification.

**Grain**: `product_key + store_key + region_key + date_key`

**Key Features**:
- ✅ Filters deals with 20%+ discount
- ✅ Quality score (0-100) based on multiple factors
- ✅ Legitimacy classification (High Quality, Good Quality, Review Required, Suspicious)
- ✅ Temporal persistence tracking (flash deal detection)
- ✅ Rankings by quality and savings

**Quality Validation Rules**:

| Rule | Weight | Description |
|------|--------|-------------|
| Optimal discount range (20-50%) | 50 pts | Sweet spot for legitimate deals |
| Non-suspicious (<70% discount) | 30 pts | Extreme discounts are flagged |
| Valid pricing (list > promotional) | 10 pts | Basic consistency check |
| Known brand | 10 pts | Brand reputation factor |

**Legitimacy Levels**:
- **High Quality** (70-100 pts): Optimal discount + known brand
- **Good Quality** (50-69 pts): Optimal discount range
- **Review Required** (30-49 pts): Needs manual verification
- **Suspicious** (0-29 pts): Likely fake or error

**Columns**:
```sql
-- Keys & Identifiers
product_key, product_id, product_name, brand, store_key, supermarket, region

-- Pricing
promotional_price, regular_price, discount_percentage, absolute_discount

-- Quality Metrics
quality_score (0-100)
legitimacy_level (High Quality | Good Quality | Review Required | Suspicious)
is_suspicious_discount (>70%)
has_invalid_price
is_optimal_discount_range (20-50%)

-- Temporal Metrics
deal_persistence_days (how many days deal appeared)
is_flash_deal (appeared only 1 day - suspicious)

-- Rankings
quality_rank (by quality score within store/date)
savings_rank (by absolute discount)
overall_rank (combined quality + savings)

-- Recommendation
is_recommended_deal (high quality, non-suspicious, persistent)
```

---

### 👁️ `vw_suspicious_hot_deals` (View)

**Description**: View of suspicious deals flagged for manual review.

**Purpose**: Data quality monitoring and fraud detection.

**Filters**:
- Legitimacy level = 'Suspicious'
- OR discount > 70%
- OR invalid pricing
- OR flash deal with >50% discount
- OR quality score < 30

**Columns**:
```sql
-- Identifiers
product_id, product_name, brand, supermarket, region, scraped_date

-- Pricing
promotional_price, regular_price, discount_percentage

-- Suspicion Details
suspicious_reasons (combined flags)
suspicion_severity (1-10 score)
review_priority (CRITICAL | HIGH | MEDIUM | LOW)

-- Flags
is_suspicious_discount
has_invalid_price
is_flash_deal
```

**Review Priority**:
- **CRITICAL**: Extreme discount (>70%) + flash deal
- **HIGH**: Extreme discount OR invalid pricing
- **MEDIUM**: Flash deal with >50% discount
- **LOW**: Low quality score

---

## Usage Examples

### 1. Get Top 10 Recommended Deals Today

```sql
SELECT
    product_name,
    brand,
    supermarket,
    promotional_price,
    regular_price,
    discount_percentage,
    quality_score,
    legitimacy_level
FROM {{ ref('fct_hot_deals_validated') }}
WHERE
    scraped_date = CURRENT_DATE
    AND is_recommended_deal = true
ORDER BY overall_rank
LIMIT 10;
```

### 2. Monitor Suspicious Deals (Quality Dashboard)

```sql
SELECT
    review_priority,
    COUNT(*) as deals_count,
    AVG(discount_percentage) as avg_discount,
    AVG(quality_score) as avg_quality_score
FROM {{ ref('vw_suspicious_hot_deals') }}
WHERE scraped_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY review_priority
ORDER BY
    CASE review_priority
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        ELSE 4
    END;
```

### 3. Analyze Deal Persistence (Detect Flash Deals)

```sql
SELECT
    product_name,
    supermarket,
    deal_persistence_days,
    discount_percentage,
    quality_score,
    legitimacy_level
FROM {{ ref('fct_hot_deals_validated') }}
WHERE
    is_flash_deal = true
    AND discount_percentage > 50
ORDER BY discount_percentage DESC
LIMIT 20;
```

### 4. Store-Level Quality Metrics

```sql
SELECT
    supermarket,
    COUNT(*) as total_hot_deals,
    COUNT(CASE WHEN is_recommended_deal THEN 1 END) as recommended_deals,
    COUNT(CASE WHEN legitimacy_level = 'Suspicious' THEN 1 END) as suspicious_deals,
    AVG(quality_score) as avg_quality_score,
    AVG(discount_percentage) as avg_discount
FROM {{ ref('fct_hot_deals_validated') }}
WHERE scraped_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY supermarket
ORDER BY avg_quality_score DESC;
```

---

## Data Quality Tests

### DBT Tests Configured:

1. **Referential Integrity**:
   - `product_key` → `dim_product`

2. **Value Constraints**:
   - `discount_percentage >= 20` (minimum hot-deal threshold)
   - `quality_score` between 0-100
   - `promotional_price > 0`
   - `regular_price > promotional_price`

3. **Business Logic**:
   - Suspicious flag matches discount > 70%
   - Legitimacy level consistency
   - Max 50 invalid pricing records (warning threshold)

4. **Data Volume**:
   - Suspicious deals < total promotions (sanity check)

### Running Tests:

```bash
# Run all hot-deals tests
dbt test --select fct_hot_deals_validated

# Run only quality tests
dbt test --select fct_hot_deals_validated,tag:quality

# Check suspicious deals
dbt test --select vw_suspicious_hot_deals
```

---

## Quality Score Calculation

**Formula**:
```
quality_score = discount_range_score (50)
              + non_suspicious_score (30)
              + valid_pricing_score (10)
              + brand_score (10)
```

**Breakdown**:
- **50 pts**: Discount in optimal range (20-50%)
- **30 pts**: Not suspicious (<70% discount)
- **10 pts**: Valid pricing (list > promotional)
- **10 pts**: Known brand (not null, length > 2)

**Thresholds**:
- **≥ 70 pts**: High Quality → Recommend
- **50-69 pts**: Good Quality → Consider
- **30-49 pts**: Review Required → Manual check
- **< 30 pts**: Suspicious → Reject

---

## Legitimacy Classification

| Level | Criteria | Action |
|-------|----------|--------|
| **High Quality** | Optimal discount (20-50%) + Known brand | ✅ **RECOMMEND** |
| **Good Quality** | Optimal discount (20-50%) | ✅ **RECOMMEND** (with caution) |
| **Review Required** | Moderate discount or unknown brand | ⚠️  **MANUAL REVIEW** |
| **Suspicious** | Extreme discount (>70%) OR invalid price | ❌ **REJECT** |

---

## Temporal Persistence

**`deal_persistence_days`**: Tracks how many days a deal has appeared.

**Why it matters**:
- **Real promotions** last 1-7 days (weekly cycles)
- **Flash deals** (1 day only) are suspicious if discount > 50%
- **Persistent deals** (7+ days) are more trustworthy

**Flash Deal Detection**:
```sql
is_flash_deal = (deal_persistence_days = 1)
```

**Recommendation Logic**:
```sql
is_recommended_deal =
    legitimacy_level IN ('High Quality', 'Good Quality')
    AND NOT is_suspicious_discount
    AND NOT is_flash_deal
    AND quality_score >= 70
```

---

## Monitoring & Alerts

### Key Metrics to Monitor:

1. **Suspicious Deals Ratio**:
   ```sql
   COUNT(is_suspicious_discount) / COUNT(*) < 0.10  -- Should be <10%
   ```

2. **Average Quality Score**:
   ```sql
   AVG(quality_score) > 60  -- Should be >60
   ```

3. **Flash Deals Count**:
   ```sql
   COUNT(is_flash_deal AND discount > 50%)  -- Monitor spikes
   ```

4. **Invalid Pricing**:
   ```sql
   COUNT(has_invalid_price)  -- Should be 0 (data quality issue)
   ```

### Recommended Alerts:

- **🚨 CRITICAL**: >50 suspicious deals in one day
- **⚠️  WARNING**: Average quality score < 50
- **ℹ️  INFO**: >100 flash deals detected

---

## Lineage

```
fct_daily_prices
    ↓
fct_active_promotions
    ↓
fct_hot_deals_validated
    ↓
vw_suspicious_hot_deals
```

---

## Future Enhancements

### Planned:
- [ ] Brand reputation scoring (external data from OpenFoodFacts)
- [ ] Category-specific discount thresholds (e.g., electronics vs groceries)
- [ ] Competitor price comparison (identify fake anchor pricing)
- [ ] ML model for anomaly detection
- [ ] Seasonal pattern analysis (holiday promotions)

### Integration:
- [ ] Export to Streamlit dashboard
- [ ] Real-time alerts via Prefect
- [ ] API endpoint for mobile app

---

## Related Documentation

- **Testing Strategy**: `docs/quality/TESTING_STRATEGY.md`
- **Data Layers**: `docs/architecture/DATA_LAYERS.md`
- **KPI Matrix**: `docs/templates/KPI_MATRIX.md`

---

**Last Updated**: 2026-02-07
**Owner**: Data Team
**Contact**: For questions, see project README
