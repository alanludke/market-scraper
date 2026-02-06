# Exploratory Data Analysis (EDA) Template

Use this template when adding a new data source to the Market Scraper platform.

---

## 1. Central Document

Create a central document consolidating all EDA findings:

| Source Name | Description | Volume Estimate | Extraction Frequency |
|-------------|-------------|-----------------|---------------------|
| VTEX API (Bistek) | Product catalog with pricing | ~10K products × 13 regions = 130K rows/day | Daily |
| *[Add new source]* | | | |

**Example for Market Scraper:**
- **Source**: VTEX API (Giassi)
- **Description**: Product catalog from 17 regions with prices, availability, and SKUs
- **Volume**: ~10K unique products × 17 regions = 170K rows/day
- **Frequency**: Daily (scheduled 2 AM)

---

## 2. Data Sources Overview

Clearly describe each data source with relevant columns and filters:

| Source Name | Relevant Columns | Applied Filters |
|-------------|------------------|-----------------|
| VTEX Products API | productId, productName, brand, items[], link | productId IS NOT NULL |
| *[Add new source]* | | |

**Example for Market Scraper:**
- **Source**: VTEX Products API
- **Columns**:
  - `productId` (string) - Unique identifier
  - `productName` (string) - Display name
  - `brand` (string, nullable) - Product brand
  - `items` (array) - SKUs with pricing/availability
  - `link` (string) - Product URL
- **Filters**:
  - `productId is not null` (basic quality)
  - Active products only (availability check)

---

## 3. Data Quality Tests

Identify and document necessary data quality tests:

| Test Type | Column(s) | Description | Priority |
|-----------|-----------|-------------|----------|
| Completeness | product_id | Check for missing IDs | High |
| Uniqueness | product_id + region + date | Ensure no duplicates per day | High |
| Accepted Values | supermarket | Must be: bistek, fort, giassi | High |
| Freshness | scraped_at | Data must be <24h old | Medium |
| Range Check | min_price | Price must be >= 0 | High |

**Template for New Source:**
```yaml
tests:
  - name: completeness_product_id
    severity: error
    query: SELECT COUNT(*) FROM source WHERE product_id IS NULL

  - name: freshness_check
    severity: warn
    query: SELECT MAX(scraped_at) FROM source
    threshold: CURRENT_TIMESTAMP - INTERVAL 24 HOURS
```

---

## 4. Data Transformations

Identify primary transformations required:

| Transformation Type | Column(s) | Details | Layer |
|---------------------|-----------|---------|-------|
| Type Casting | productId → product_id | string | Staging |
| Normalization | brand | UPPER(TRIM(brand)) | Staging |
| Flattening | items[] → SKUs | unnest(items) | Trusted |
| Deduplication | product_id + region | Keep latest scraped_at | Trusted |
| Aggregation | prices | MIN/AVG/MAX per product | Marts |

**Example Transformation:**
```sql
-- Staging: Cast and rename
cast(productId as string) as product_id

-- Trusted: Flatten nested array
unnest(items) as item

-- Marts: Aggregate pricing
min(item.price) as min_price,
avg(item.price) as avg_price
```

---

## 5. Granularity Check

Verify and document the granularity of data:

| Data Source | Granularity | Consistency Check |
|-------------|-------------|-------------------|
| VTEX Products | Product × Region × Day | ✅ Verified: unique per day |
| Pricing History | Product × Region × Hour | ⚠️ Needs dedup to daily |

**Granularity Questions:**
- What is the finest level of detail? (transaction, daily aggregate, etc.)
- Does it match business requirements?
- Are there unexpected duplicates?

---

## 6. Key Identification

Document primary and foreign keys for each data source:

| Table Name | Primary Key | Foreign Key(s) | Relationship |
|------------|-------------|----------------|--------------|
| tru_product | product_id + region + scraped_date | - | - |
| fct_prices_daily | price_id | product_id → tru_product | Many-to-One |
| dim_stores | store_id | - | - |

**Key Validation:**
```sql
-- Check primary key uniqueness
SELECT product_id, region, scraped_date, COUNT(*)
FROM tru_product
GROUP BY 1, 2, 3
HAVING COUNT(*) > 1;

-- Check foreign key integrity
SELECT DISTINCT p.product_id
FROM fct_prices_daily p
LEFT JOIN tru_product t ON p.product_id = t.product_id
WHERE t.product_id IS NULL;
```

---

## 7. Data Volume Estimation

Provide detailed data volume estimates:

| Data Source | Historical Size | Daily Increment | Growth Projection | Storage Format |
|-------------|-----------------|-----------------|-------------------|----------------|
| Bronze (Parquet) | 8MB (all history) | 50KB/day | ~20MB/year | Snappy compressed |
| Trusted (DuckDB) | 15MB | 100KB/day | ~35MB/year | Columnar |
| Marts (DuckDB) | 5MB | 30KB/day | ~10MB/year | Pre-aggregated |

**Calculations:**
```
Daily Products: 10K products × 3 stores × 15 avg regions = 450K rows
Parquet Size: 450K rows × ~100 bytes/row compressed = ~45KB/day
Annual Growth: 45KB × 365 days = ~16MB/year
```

---

## 8. Sensitive Data Visibility

Identify and highlight sensitive data:

| Data Source | Column | Type of Sensitivity | Compliance | Mitigation |
|-------------|--------|---------------------|------------|------------|
| VTEX Products | ❌ None | Public e-commerce data | N/A | - |
| *[Add new source]* | customer_email | PII | GDPR | Hash/redact |

**Market Scraper Assessment:**
- ✅ **No PII**: Product pricing data only
- ✅ **Public sources**: E-commerce catalog APIs
- ✅ **No credentials**: API keys in `.env` (gitignored)

**If adding PII in future:**
- Implement column-level encryption
- Add `contains_pii: true` to model metadata
- Restrict access (row-level security)
- Document in compliance registry

---

## 9. Data Risks and Issues

Document identified risks or potential data failures:

| Risk/Issue | Description | Impact | Mitigation | Status |
|------------|-------------|--------|------------|--------|
| API Rate Limits | VTEX limits: 600 req/min | Scrape failures | Batch requests, exponential backoff | ✅ Implemented |
| Schema Changes | API adds/removes fields | Pipeline breaks | Monitor schema, version API responses | ⚠️ Manual check |
| Empty Structs | Nested fields with no data | Parquet serialization fails | Pre-clean empty dicts | ✅ Implemented |
| Regional Availability | Products missing in some regions | Incomplete data | Accept nulls, flag as unavailable | ✅ Handled |

**Example Risk Documentation:**
```markdown
### Risk: API Schema Change

**Description**: VTEX adds new field `promotionDetails` to product response.

**Impact**:
- Low: DBT models continue (schema-on-read)
- Medium: May miss new insights

**Mitigation**:
1. Weekly API response diff check
2. Alerting on new fields detected
3. Version API calls (/v1, /v2)

**Status**: ⚠️ Monitoring needed
```

---

## 10. Sample Data

Provide representative sample data:

**Bronze (Raw JSON→Parquet):**
```json
{
  "productId": "12345",
  "productName": "Arroz Integral 1kg",
  "brand": "Tio João",
  "items": [
    {
      "itemId": "67890",
      "name": "Arroz Integral 1kg",
      "ean": "7891234567890",
      "sellers": [{
        "commertialOffer": {
          "Price": 8.99,
          "ListPrice": 10.99,
          "AvailableQuantity": 150
        }
      }]
    }
  ],
  "_metadata_supermarket": "bistek",
  "_metadata_region": "florianopolis_costeira",
  "_metadata_scraped_at": "2026-02-05T14:32:00Z"
}
```

**Trusted (Flattened):**
```sql
product_id | product_name          | brand     | min_price | is_available | scraped_date
-----------|----------------------|-----------|-----------|--------------|-------------
12345      | Arroz Integral 1kg   | Tio João  | 8.99      | true         | 2026-02-05
```

---

## Final Checks

Before completing EDA:

- [ ] All 10 sections thoroughly completed
- [ ] Sample queries tested and validated
- [ ] Data quality tests defined in DBT
- [ ] Volume estimates confirmed (actual vs projected)
- [ ] Risks documented with mitigation plans
- [ ] Stakeholders reviewed findings
- [ ] Schema documented in `schema.yml`
- [ ] README updated with new source

---

## EDA Review Meeting Template

**Attendees**: Data Engineer, Data Analyst, Product Owner

**Agenda**:
1. Data Source Overview (5 min)
2. Volume & Freshness (5 min)
3. Quality Concerns (10 min)
4. Transformation Logic (10 min)
5. Risks & Mitigations (5 min)
6. Q&A (5 min)

**Decision**: ✅ Approved / ⚠️ Needs revision / ❌ Blocked

---

## Example: Complete EDA for New Store

```markdown
# EDA: Angeloni Supermarket

## 1. Central Document
- **Source**: VTEX API (Angeloni)
- **Volume**: ~8K products × 12 regions = 96K rows/day
- **Frequency**: Daily at 3 AM

## 2. Data Sources
- **API Endpoint**: `https://angeloni.com.br/api/catalog_system/pub/products/search`
- **Columns**: Same as Bistek (VTEX platform)
- **Filters**: Active products only

## 3. Quality Tests
- ✅ Not null: product_id, product_name
- ✅ Unique: product_id + region + date
- ✅ Accepted values: supermarket = 'angeloni'
- ✅ Freshness: <24h

## 4. Transformations
- Staging: Cast, rename (same as other VTEX stores)
- Trusted: Dedup by (product_id, region, date)
- Marts: Aggregate pricing

## 5. Granularity
- Product × Region × Day (consistent with other stores)

## 6. Keys
- PK: product_id + region + scraped_date
- FK: None (dimension table)

## 7. Volume
- Daily: ~50KB Parquet
- Annual: ~18MB

## 8. Sensitive Data
- ❌ None (public pricing)

## 9. Risks
- ⚠️ API authentication changed (needs new token)
- ⚠️ Some regions have sparse data (<100 products)

## 10. Sample Data
[Include JSON sample]

**Decision**: ✅ Approved - Proceed with implementation
```

---

## Resources

- [Data Quality Testing](../quality/TESTING_STRATEGY.md)
- [Data Layers](../architecture/DATA_LAYERS.md)
- [DBT Best Practices](https://docs.getdbt.com/best-practices)
