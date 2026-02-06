# Project Quality Standards - Market Scraper

## Overview

This document defines the quality standards and governance practices for the Market Scraper project. We ensure **code quality**, **documentation completeness**, and **structural consistency** through automated validations and CI/CD enforcement.

---

## Quality Principles

### 1. Governance

A set of standards and guidelines that ensure our data models are **consistent**, **well-documented**, and **trustworthy**:

- ✅ Code formatting and structure
- ✅ Documentation completeness
- ✅ Semantic naming conventions
- ✅ Modular and reusable logic
- ✅ Data quality validation

**Enforcement**: Automated via **pre-commit hooks** and **CI/CD pipelines**.

---

## Quality Layers

| Layer                 | Tool               | Purpose                                    | Frequency       |
| --------------------- | ------------------ | ------------------------------------------ | --------------- |
| SQL Linting           | `sqlfluff`         | Enforce SQL style, readability             | Pre-commit, CI  |
| YAML Validation       | `yamllint`         | Ensure clean metadata files                | Pre-commit, CI  |
| DBT Best Practices    | `dbt-checkpoint`   | Guarantee documentation, naming            | Pre-commit, CI  |
| Data Testing          | `dbt test`         | Validate data integrity, business rules    | CI, Nightly     |
| Workflow Automation   | GitHub Actions     | Enforce compliance at every commit/PR      | CI (on PR)      |

---

## Tools & Configuration

### 1. SQLFluff (SQL Linting)

**Purpose**: Enforce SQL syntax consistency, style guidelines, and readability across all DBT models.

**Prevents**:
- Improper indentation
- Non-standard naming
- Lack of clarity in expressions
- Use of deprecated syntax

**Configuration**: `.sqlfluff` in `src/transform/dbt_project/`

**Key Rules**:
- **Dialect**: DuckDB
- **Capitalization**: lowercase (keywords, functions, identifiers)
- **Indentation**: 4 spaces
- **Line length**: 150 characters max
- **Comma style**: Leading commas

**Example (Well-Formatted SQL)**:
```sql
{{ config(materialized='table') }}

with source_products as (
    select *
    from {{ source('bronze_bistek', 'products') }}
)

, renamed_products as (
    select
        cast(productId as varchar) as product_id
        , cast(productName as varchar) as product_name
        , cast(brand as varchar) as brand
        , case
            when brand is null then 'Generic'
            else upper(trim(brand))
        end as brand_clean
        , cast(items as json) as items_json
        , date_trunc('day', scraped_at) as scraped_date
        , cast(scraped_at as timestamp) as scraped_at
        , '_metadata_supermarket' as system_name

    from source_products
    where product_id is not null
)

select *
from renamed_products
```

**Running SQLFluff**:
```bash
# Lint SQL files
cd src/transform/dbt_project
sqlfluff lint models/ --dialect duckdb

# Auto-fix issues
sqlfluff fix models/ --dialect duckdb

# Lint specific model
sqlfluff lint models/trusted/tru_product.sql
```

---

### 2. YAMLLint (YAML Validation)

**Purpose**: Ensure YAML files (schemas, sources, docs) are syntactically correct and follow formatting conventions.

**Critical for**:
- Model documentation (`schema.yml`)
- Source declarations (`sources.yml`)
- DBT project config (`dbt_project.yml`)

**Configuration**: `.yamllint` in `src/transform/dbt_project/`

**Key Rules**:
- **Indentation**: 2 spaces
- **Line length**: 250 characters (warning)
- **Empty values**: Allowed
- **Trailing spaces**: Not allowed
- **New line at EOF**: Required

**Example (Well-Formatted YAML)**:
```yaml
version: 2

models:
  - name: tru_product
    description: >
      Trusted model de produtos com lógica de negócio aplicada.
      Deduplica scrapes diários por produto+região e extrai pricing de SKUs.
    config:
      meta:
        graining: product_region_date
        contains_pii: false
        table_owner: Data Engineering
        email_owner: data-engineering@market-scraper.local
        model_maturity: medium
        access_type: public
        load_frequency: daily
        main_kpis: min_price, avg_price, is_available, sku_count
    columns:
      - name: product_id
        description: Unique product identifier from VTEX API
        data_type: varchar
        tests:
          - not_null
          - unique:
              config:
                where: "scraped_date = current_date"

      - name: product_name
        description: Product name as displayed in e-commerce
        data_type: varchar
        tests:
          - not_null

      - name: min_price
        description: Minimum price across all SKUs for this product
        data_type: double
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 100000
```

**Running YAMLLint**:
```bash
# Lint YAML files
cd src/transform/dbt_project
yamllint -c .yamllint models/

# Lint specific file
yamllint models/trusted/schema.yml
```

---

### 3. DBT Checkpoint (DBT Best Practices)

**Purpose**: Enforce DBT-specific best practices (documentation, naming, testing).

**Configuration**: `.pre-commit-config.yaml` in `src/transform/dbt_project/`

**Hooks Configured**:

#### `dbt-parse`
Ensures DBT project compiles without errors.

#### `check-script-semicolon`
Prevents semicolons in SQL (not needed in DBT).

#### `check-model-columns-have-desc`
Ensures all columns in **trusted** and **marts** layers have descriptions.

**Exception**: Staging layer (ephemeral) not enforced.

#### `check-model-has-description`
Ensures all models have top-level descriptions.

#### `check-model-has-meta-keys`
Validates metadata completeness:
- **Trusted**: `graining`, `owner`, `access_type`, `contains_pii`, `main_kpis`
- **Marts**: Same + `product_usage`

#### `check-model-name-contract`
Validates naming conventions:
- **Staging**: `stg_<source>__<entity>` (e.g., `stg_vtex__products`)
- **Trusted**: `tru_<entity>` (e.g., `tru_product`)
- **Marts**: `fct_<process>` or `dim_<entity>` (e.g., `fct_prices_daily`, `dim_product`)

**Example Validation**:
```yaml
# ✅ PASS: models/staging/stg_vtex__products.sql
# ✅ PASS: models/trusted/tru_product.sql
# ✅ PASS: models/marts/fct_prices_daily.sql
# ❌ FAIL: models/trusted/product.sql (missing 'tru_' prefix)
# ❌ FAIL: models/marts/sales.sql (missing 'fct_' or 'dim_' prefix)
```

**Running Pre-commit Hooks**:
```bash
# Install pre-commit
pip install pre-commit

# Install hooks
cd src/transform/dbt_project
pre-commit install

# Run manually
pre-commit run --all-files

# Run specific hook
pre-commit run dbt-parse
```

---

### 4. DBT Tests (Data Quality)

**Purpose**: Validate data integrity and business rules.

**Test Types**:

#### Generic Tests (Built-in)
- `not_null`: Column has no NULL values
- `unique`: Column values are unique
- `accepted_values`: Column values are from allowed list
- `relationships`: Foreign key integrity

#### Custom Tests (dbt-utils)
- `accepted_range`: Numeric values within range
- `recency`: Data freshness check
- `unique_combination_of_columns`: Composite key uniqueness
- `expression_is_true`: Business rule validation

**Example Tests** (`models/trusted/schema.yml`):
```yaml
models:
  - name: tru_product
    tests:
      # Unique composite key
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns:
            - product_id
            - region
            - scraped_date

      # Business rule: min_price <= avg_price
      - dbt_utils.expression_is_true:
          expression: "min_price <= avg_price"

      # Freshness: data updated in last 48 hours
      - dbt_utils.recency:
          datepart: hour
          field: scraped_at
          interval: 48

    columns:
      - name: product_id
        tests:
          - not_null
          - unique:
              config:
                where: "scraped_date = current_date"

      - name: supermarket
        tests:
          - accepted_values:
              values: ['bistek', 'fort', 'giassi']

      - name: min_price
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 100000
```

**Running Tests**:
```bash
# Run all tests
cd src/transform/dbt_project
dbt test

# Test specific model
dbt test --select tru_product

# Test specific test type
dbt test --select test_type:unique
dbt test --select test_type:not_null
```

---

### 5. GitHub Actions (CI/CD Automation)

**Purpose**: Enforce quality standards automatically on every PR.

**Workflows**:

#### `.github/workflows/lint.yml`
Runs on PRs, validates SQL and YAML:
```yaml
jobs:
  sqlfluff-lint:
    - name: Lint SQL files
      run: sqlfluff lint models/ --dialect duckdb

  yamllint:
    - name: Lint YAML files
      run: yamllint -c .yamllint models/
```

#### `.github/workflows/test.yml`
Runs on PRs, validates DBT models:
```yaml
jobs:
  dbt-test:
    - name: DBT Parse
      run: dbt parse

    - name: DBT Compile
      run: dbt compile

    # Uncomment when bronze data in CI
    # - name: DBT Test
    #   run: dbt test
```

**Trigger**: Automatically on PR to `main`/`master`

**Required Checks**: PRs **cannot merge** unless workflows pass.

---

## Quality Checklist (Before Merge)

Use this checklist before creating a PR:

### Code Quality
- [ ] SQL passes `sqlfluff lint` (no errors)
- [ ] YAML passes `yamllint` (no errors)
- [ ] `dbt parse` successful
- [ ] `dbt compile` successful
- [ ] All `pre-commit` hooks pass

### Documentation
- [ ] Model has `description` in `schema.yml`
- [ ] All columns documented (trusted/marts layers)
- [ ] Meta tags complete (`graining`, `owner`, `contains_pii`, etc.)
- [ ] README updated (if new feature)

### Testing
- [ ] Primary keys have `unique` + `not_null` tests
- [ ] Foreign keys have `relationships` tests
- [ ] Business rules have `expression_is_true` tests
- [ ] Freshness checks for time-sensitive data
- [ ] All tests pass (`dbt test`)

### Naming Conventions
- [ ] Staging models: `stg_<source>__<entity>`
- [ ] Trusted models: `tru_<entity>`
- [ ] Marts models: `fct_<process>` or `dim_<entity>`
- [ ] Columns: snake_case, descriptive names
- [ ] Booleans: `is_<attribute>` or `has_<attribute>`

### Performance
- [ ] Incremental models use watermarking (`is_incremental()`)
- [ ] Large tables have `on_schema_change='append_new_columns'`
- [ ] No unnecessary full table scans
- [ ] Filters applied early in CTEs

---

## Workflow Automation

### Pre-commit Hooks (Local)

**When**: Before `git commit`

**What**:
1. SQL linting (`sqlfluff`)
2. YAML validation (`yamllint`)
3. DBT best practices (`dbt-checkpoint`)
4. File formatting (trailing whitespace, EOF)

**Installation**:
```bash
cd src/transform/dbt_project
pip install pre-commit
pre-commit install
```

**Bypassing** (NOT RECOMMENDED):
```bash
git commit --no-verify  # Skip pre-commit hooks
```

---

### CI/CD Pipeline (GitHub Actions)

**When**: On PR to `main`/`master`

**Stages**:
1. **Lint**: SQL + YAML validation
2. **Parse**: DBT project compiles
3. **Compile**: SQL generation successful
4. **Test**: Data quality tests pass (when bronze data available)

**Failure Handling**: PR blocked from merge until all checks pass.

**Manual Trigger**:
```bash
# Run workflow manually via GitHub UI
# Actions → Select workflow → Run workflow
```

---

## Continuous Improvement

### Monthly Quality Audit

Run this monthly audit to ensure standards are maintained:

```bash
# 1. Check SQL linting compliance
cd src/transform/dbt_project
sqlfluff lint models/ --dialect duckdb

# 2. Check YAML compliance
yamllint -c .yamllint models/

# 3. Check documentation coverage
dbt docs generate
# Open: target/index.html
# Verify: All models have descriptions

# 4. Check test coverage
dbt test
# Review: models/tests/ directory
# Verify: All critical columns tested

# 5. Check naming conventions
ls models/staging/  # All stg_*
ls models/trusted/  # All tru_*
ls models/marts/    # All fct_* or dim_*
```

### Metrics to Track

| Metric                  | Target | Current | Status |
| ----------------------- | ------ | ------- | ------ |
| SQL Lint Pass Rate      | 100%   | 100%    | ✅     |
| YAML Lint Pass Rate     | 100%   | 100%    | ✅     |
| Documentation Coverage  | 100%   | 100%    | ✅     |
| Test Coverage (Models)  | 100%   | 100%    | ✅     |
| Test Coverage (Columns) | 80%+   | 85%     | ✅     |
| CI/CD Pass Rate         | 95%+   | 100%    | ✅     |

---

## Troubleshooting

### "SQLFluff lint failed"

**Symptom**: Pre-commit or CI fails with SQL linting errors.

**Fix**:
```bash
# Auto-fix issues
sqlfluff fix models/trusted/tru_product.sql

# View specific errors
sqlfluff lint models/trusted/tru_product.sql --verbose
```

### "YAMLLint errors on schema.yml"

**Symptom**: Indentation or formatting issues.

**Fix**:
```bash
# Check errors
yamllint models/trusted/schema.yml

# Common issues:
# - Mixed tabs/spaces (use 2 spaces)
# - Line too long (break into multiline with '>

')
# - Trailing whitespace (remove)
```

### "dbt-checkpoint: Model name violation"

**Symptom**: Model doesn't follow naming convention.

**Fix**:
- Staging: Rename to `stg_<source>__<entity>`
- Trusted: Rename to `tru_<entity>`
- Marts: Rename to `fct_<process>` or `dim_<entity>`

### "dbt test failed: unique constraint"

**Symptom**: Duplicate records in model.

**Fix**:
```sql
-- Add deduplication logic
WITH deduplicated AS (
    SELECT * EXCLUDE rn
    FROM (
        SELECT *,
            ROW_NUMBER() OVER (
                PARTITION BY product_id, region, scraped_date
                ORDER BY scraped_at DESC
            ) as rn
        FROM source
    )
    WHERE rn = 1
)
SELECT * FROM deduplicated
```

---

## Summary

Our quality strategy ensures:

| Goal                 | Implementation                                    | Result                      |
| -------------------- | ------------------------------------------------- | --------------------------- |
| **Consistency**      | SQLFluff + YAMLLint                               | Readable, maintainable code |
| **Documentation**    | dbt-checkpoint (mandatory descriptions)           | Self-documenting project    |
| **Correctness**      | dbt tests (data integrity)                        | Trusted data                |
| **Enforcement**      | Pre-commit hooks + CI/CD                          | Compliance at every commit  |
| **Scalability**      | Automated validations (no manual reviews needed)  | Fast iteration              |

By combining these tools with a strong culture of quality, we ensure our project is **robust**, **maintainable**, and **ready to scale**.

---

## References

- [SQLFluff Documentation](https://docs.sqlfluff.com/)
- [YAMLLint Documentation](https://yamllint.readthedocs.io/)
- [dbt-checkpoint Documentation](https://github.com/dbt-checkpoint/dbt-checkpoint)
- [DBT Testing Best Practices](https://docs.getdbt.com/docs/build/tests)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
