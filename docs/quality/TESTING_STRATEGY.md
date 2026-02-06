# Testing Strategy - DBT Data Tests

## Why Test Data?

In dbt, **data testing** helps ensure that your transformations are correct and trustworthy. Just like software engineering uses tests to catch bugs early, data testing helps validate assumptions and avoid costly errors in pipelines.

Data tests in dbt are **assertions** about your data. They don't transform anything — they check that your data meets certain conditions.

---

## Generic Tests (Pre-built)

dbt comes with a set of **built-in generic tests** that can be applied directly in your `schema.yml` files. These are great for validating common data quality rules without writing custom SQL.

### Available Generic Tests

1. **`not_null`** - Checks that a column does not contain any null values
2. **`unique`** - Checks that all values are unique (no duplicates)
3. **`accepted_values`** - Checks that values are within a predefined list
4. **`relationships`** - Checks foreign key relationships to other tables

---

## 1. `not_null` Test

**What it does:**
Checks that a column **does not contain any null values**.

**When to use:**
Primary keys, required fields, or foreign keys.

**Example:**

```yaml
columns:
  - name: product_id
    data_tests:
      - not_null
```

### Incremental Model Testing

For incremental models, you can set time windows to test recent data only. This is useful for large tables where testing all historical data is expensive.

**Note:** For uniqueness tests, always test the full table to avoid duplicate data insertion.

```yaml
columns:
  - name: product_id
    data_tests:
      - not_null:
          config:
            where: "scraped_at >= dateadd(day, -7, current_timestamp())"
            severity: error
```

---

## 2. `unique` Test

**What it does:**
Checks that all values in a column are **unique** (no duplicates).

**When to use:**
Primary key fields or identifiers that must not repeat.

**Example:**

```yaml
columns:
  - name: product_id
    data_tests:
      - unique
```

**Market Scraper Example:**

```yaml
# tru_product.yml
columns:
  - name: product_id
    data_tests:
      - unique:
          config:
            where: "scraped_date = current_date"  # Unique per day only
```

---

## 3. `accepted_values` Test

**What it does:**
Checks that all values in a column are **within a predefined list**.

**When to use:**
Columns that should only have a known set of values (e.g., status, region, supermarket).

**Example:**

```yaml
columns:
  - name: supermarket
    data_tests:
      - accepted_values:
          values: ['bistek', 'fort', 'giassi']
```

**Market Scraper Example:**

```yaml
# stg_vtex__products.yml
columns:
  - name: region
    data_tests:
      - accepted_values:
          values: [
            'florianopolis_costeira',
            'florianopolis_continental',
            'florianopolis_santa_monica',
            'florianopolis_trindade'
          ]
```

---

## 4. `relationships` Test

**What it does:**
Checks that all values in a column **exist in a related table's column** (foreign key validation).

**When to use:**
When a column should reference a valid record from another table.

**Example:**

```yaml
columns:
  - name: product_id
    data_tests:
      - relationships:
          to: ref('dim_products')
          field: product_id
```

**Market Scraper Example:**

```yaml
# fct_prices_daily.yml
columns:
  - name: product_id
    description: Foreign key to tru_product
    data_tests:
      - relationships:
          to: ref('tru_product')
          field: product_id

  - name: store_id
    description: Foreign key to dim_stores
    data_tests:
      - relationships:
          to: ref('dim_stores')
          field: store_id
```

---

## Where Tests Should Live

To keep your project organized and test efficiently, follow these guidelines:

### 🔸 Source-Level Tests

Sources can have **freshness tests** to validate that data is being ingested on schedule.

```yaml
sources:
  - name: bronze_bistek
    description: Bronze layer data from Bistek supermarket
    freshness:
      warn_after:
        count: 2
        period: day
      error_after:
        count: 3
        period: day
    loaded_at_field: _metadata_scraped_at
    tables:
      - name: products
        description: Raw product catalog with prices per region
```

**For Market Scraper:**
- Warn if data is > 2 days old
- Error if data is > 3 days old
- Check `_metadata_scraped_at` field

### 🔸 Staging Models

Tests here validate **cleaned and conformed** versions of your source data.

**What to test:**
- Data formatting (casts, type conversions)
- ID presence and uniqueness
- Accepted values for categorical fields

**Market Scraper Example:**

```yaml
# stg_vtex__products.yml
models:
  - name: stg_vtex__products
    columns:
      - name: product_id
        data_tests:
          - not_null
          - unique

      - name: supermarket
        data_tests:
          - not_null
          - accepted_values:
              values: ['bistek', 'fort', 'giassi']

      - name: scraped_at
        data_tests:
          - not_null
```

### 🔸 Trusted Models

Tests in the **trusted** layer validate the conformed view of data that serves as foundation for downstream consumers.

**What to test:**
- Primary keys (uniqueness + not_null)
- Source conformance (unioned sources align correctly)
- Translated values (nulls handled correctly)
- Categorical mappings (derived fields match expected sets)

**Market Scraper Example:**

```yaml
# tru_product.yml
models:
  - name: tru_product
    columns:
      - name: product_id
        data_tests:
          - not_null
          - unique:
              config:
                where: "scraped_date = current_date"

      - name: min_price
        data_tests:
          - not_null
          - dbt_utils.expression_is_true:
              expression: "min_price > 0"

      - name: is_available
        data_tests:
          - not_null
          - accepted_values:
              values: [true, false]
```

### 🔸 Business Logic (Marts)

Here, test your **business rules and assumptions**.

**What to test:**
- Metrics align with expected ranges
- Segmentations are mutually exclusive
- Aggregations are consistent
- Foreign key relationships

**Market Scraper Example:**

```yaml
# fct_prices_daily.yml
models:
  - name: fct_prices_daily
    columns:
      - name: price_usd
        data_tests:
          - not_null
          - dbt_utils.expression_is_true:
              expression: "price_usd >= 0"

      - name: price_variance_pct
        data_tests:
          - dbt_utils.expression_is_true:
              expression: "price_variance_pct BETWEEN -100 AND 100"

      - name: product_id
        data_tests:
          - relationships:
              to: ref('tru_product')
              field: product_id

      - name: region_id
        data_tests:
          - relationships:
              to: ref('dim_regions')
              field: region_id
```

---

## Test Smarter, Not Harder

### Don't Overtest

Testing every column of every model with `not_null` or `unique` often leads to noise. Be intentional:

- Focus on **business-critical logic**
- Avoid testing derived/nullable fields unless they must meet conditions
- Don't test intermediate CTEs (test final output only)

### Use Tests to Protect Against Regression

Place tests near logic that could break due to:

- Changes in upstream systems (API schema changes)
- Incorrect joins or filters
- Business rule changes
- Edge cases (empty strings, zero values, negative prices)

### Version and Label Your Tests

Use clear descriptions and maintain tests just like models:

```yaml
columns:
  - name: price_usd
    description: >
      Price in USD at time of scrape.
      Must be non-negative. Null indicates unavailable/out-of-stock.
    data_tests:
      - not_null:
          config:
            where: "is_available = true"
            severity: error
      - dbt_utils.expression_is_true:
          expression: "price_usd >= 0"
          config:
            severity: error
```

---

## Advanced Testing Patterns

### Custom Generic Tests

Create reusable tests for common patterns:

```sql
-- tests/generic/test_price_not_negative.sql
{% test price_not_negative(model, column_name) %}

select
    {{ column_name }} as invalid_price
from {{ model }}
where {{ column_name }} < 0

{% endtest %}
```

Usage:

```yaml
columns:
  - name: min_price
    data_tests:
      - price_not_negative
```

### Singular Data Tests

For one-off business logic validations:

```sql
-- tests/fct_prices_daily_consistent_aggregation.sql
-- Validate that daily aggregates match raw data totals

with
    daily_aggregates as (
        select
            sum(price_usd) as total_price_sum,
            count(*) as total_records
        from {{ ref('fct_prices_daily') }}
        where price_date = current_date
    ),

    raw_data as (
        select
            sum(min_price) as total_price_sum,
            count(*) as total_records
        from {{ ref('tru_product') }}
        where scraped_date = current_date
    )

select *
from daily_aggregates
where
    total_price_sum != (select total_price_sum from raw_data)
    or total_records != (select total_records from raw_data)
```

---

## Best Practices Summary

| ✅ Do This | ❌ Avoid This |
|---|---|
| Test sources for freshness | Blindly applying `not_null` to every column |
| Use generic tests in `schema.yml` | Duplicating test logic in multiple models |
| Create custom tests for repeatable logic | Overloading models with redundant tests |
| Focus on business logic validations | Ignoring model-level relationships |
| Test primary keys thoroughly | Testing every derived field |
| Use incremental time windows for large tables | Testing all historical data every time |

---

## Testing Checklist

Before merging a PR with new models:

- [ ] Primary keys have `unique` + `not_null` tests
- [ ] Foreign keys have `relationships` tests
- [ ] Categorical fields have `accepted_values` tests
- [ ] Business metrics have range validation (e.g., `price >= 0`)
- [ ] All tests pass locally (`dbt test`)
- [ ] Test descriptions are clear and updated
- [ ] No unnecessary tests on derived/nullable fields

---

## Running Tests

```bash
cd src/transform/dbt_project

# Run all tests
PYTHONUTF8=1 dbt test

# Run tests for specific model
PYTHONUTF8=1 dbt test --select tru_product

# Run tests for specific tag
PYTHONUTF8=1 dbt test --select tag:pricing

# Run only failed tests
PYTHONUTF8=1 dbt test --select result:fail
```

---

## References

- [dbt Docs - Data Tests](https://docs.getdbt.com/docs/build/data-tests)
- [Test Smarter - Where Tests Should Go](https://docs.getdbt.com/blog/test-smarter-where-tests-should-go)
- [dbt Utils Package](https://hub.getdbt.com/dbt-labs/dbt_utils/latest/)
