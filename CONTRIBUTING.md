# Contributing to Market Scraper

Thank you for your interest in contributing to Market Scraper! 🎉

This document provides guidelines for contributing to the project. Please read it before submitting your contribution.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Pull Request Process](#pull-request-process)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)

---

## Code of Conduct

By participating in this project, you agree to maintain a respectful and collaborative environment. We expect:

- ✅ Respectful communication
- ✅ Constructive feedback
- ✅ Patience with beginners
- ❌ No harassment or discrimination

---

## How to Contribute

### Types of Contributions

We welcome:

- 🐛 **Bug fixes**: Fix issues in scrapers, DBT models, or analytics
- ✨ **Features**: Add new stores, metrics, or transformations
- 📖 **Documentation**: Improve guides, add examples, fix typos
- 🧪 **Tests**: Add data quality tests, unit tests, integration tests
- 🎨 **UI/UX**: Enhance Streamlit dashboards

### Not Sure Where to Start?

Check out:
- [Open Issues](https://github.com/alanludke/market-scraper/issues) labeled `good first issue`
- [Roadmap](README.md#-roadmap) for upcoming features
- Documentation gaps (missing examples, unclear sections)

---

## Development Setup

### Prerequisites

- Python 3.11+
- Git
- DBT Core 1.9+ with DuckDB adapter
- SQLFluff (for linting)
- Pre-commit (for hooks)

### Setup Steps

1. **Fork the repository** on GitHub

2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/market-scraper.git
   cd market-scraper
   ```

3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/alanludke/market-scraper.git
   ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment** (Windows):
   ```powershell
   [System.Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'User')
   # Restart terminal
   ```

6. **Install pre-commit hooks**:
   ```bash
   cd src/transform/dbt_project
   pip install pre-commit
   pre-commit install
   ```

7. **Verify setup**:
   ```bash
   dbt debug
   dbt parse
   ```

---

## Coding Standards

### SQL (DBT Models)

Follow [SQLFluff](https://sqlfluff.com/) rules:

✅ **DO**:
```sql
{{ config(materialized='table') }}

with source_data as (
    select
        product_id
        , product_name
        , min(price) as min_price
    from {{ ref('stg_vtex__products') }}
    where product_id is not null
    group by 1, 2
)

select * from source_data
```

❌ **DON'T**:
```sql
-- No config
SELECT productId, productName, MIN(price) minPrice  -- Mixed case, no commas
FROM stg_vtex__products WHERE productId IS NOT NULL GROUP BY productId, productName  -- Long line
```

**Key Rules**:
- Lowercase keywords, identifiers, functions
- 4-space indentation
- Leading commas
- Max 150 characters per line
- One CTE per logical step

📖 **Full guide**: [PROJECT_QUALITY_STANDARDS.md](docs/quality/PROJECT_QUALITY_STANDARDS.md)

---

### YAML (DBT Schemas)

Follow [yamllint](https://yamllint.readthedocs.io/) rules:

✅ **DO**:
```yaml
version: 2

models:
  - name: tru_product
    description: >
      Trusted product model with business logic.
    columns:
      - name: product_id
        description: Unique product identifier
        tests:
          - not_null
          - unique
```

❌ **DON'T**:
```yaml
version: 2
models:
- name: tru_product
  description: Trusted product model with business logic.  # No multiline
  columns:
  - name: product_id
    description: Unique product identifier
    tests: [not_null, unique]  # Use explicit YAML list
```

**Key Rules**:
- 2-space indentation
- Multiline descriptions with `>`
- Max 250 characters per line
- New line at end of file

---

### Python (Scrapers)

Follow [PEP 8](https://pep8.org/):

✅ **DO**:
```python
from typing import List, Dict

def scrape_products(store: str, limit: int = 1000) -> List[Dict]:
    """
    Scrape products from store.

    Args:
        store: Store identifier (bistek, fort, giassi)
        limit: Maximum products to scrape

    Returns:
        List of product dictionaries
    """
    products = []
    # ... scraping logic
    return products
```

❌ **DON'T**:
```python
def scrapeProducts(store,limit=1000):  # camelCase, no type hints
    products=[]  # No spaces around operators
    #... scraping logic
    return products  # No docstring
```

---

### Naming Conventions

| Type              | Convention              | Example                 |
| ----------------- | ----------------------- | ----------------------- |
| **Staging models** | `stg_<source>__<entity>` | `stg_vtex__products`    |
| **Trusted models** | `tru_<entity>`           | `tru_product`           |
| **Fact tables**    | `fct_<process>`          | `fct_prices_daily`      |
| **Dimensions**     | `dim_<entity>`           | `dim_product`           |
| **Python files**   | `snake_case`             | `vtex_scraper.py`       |
| **Functions**      | `snake_case`             | `scrape_products()`     |
| **Classes**        | `PascalCase`             | `VTEXScraper`           |
| **Constants**      | `UPPER_SNAKE_CASE`       | `MAX_RETRIES`           |

---

## Pull Request Process

### Before Creating PR

1. **Create feature branch**:
   ```bash
   git checkout -b feature/add-new-store
   ```

2. **Make changes** following coding standards

3. **Run quality checks**:
   ```bash
   cd src/transform/dbt_project

   # Lint SQL
   sqlfluff lint models/ --dialect duckdb

   # Lint YAML
   yamllint -c .yamllint models/

   # Run pre-commit hooks
   pre-commit run --all-files

   # Parse DBT
   dbt parse

   # Compile DBT
   dbt compile

   # Test data quality
   dbt test
   ```

4. **Commit with clear message**:
   ```bash
   git add .
   git commit -m "feat: add Angeloni supermarket scraper"
   ```

### Creating the PR

1. **Push to your fork**:
   ```bash
   git push origin feature/add-new-store
   ```

2. **Open PR** on GitHub with:
   - **Title**: `<type>: <short description>` (e.g., `feat: add Angeloni scraper`)
   - **Description**: Follow [PR_CHECKLIST.md](docs/templates/PR_CHECKLIST.md)

3. **Fill out checklist**:
   - [ ] Tests pass (`dbt test`)
   - [ ] Linting passes (SQLFluff, yamllint)
   - [ ] Documentation updated
   - [ ] CI/CD passes

### PR Review Process

1. **Automated checks** run (GitHub Actions)
2. **Maintainer reviews** code
3. **Address feedback** via new commits
4. **Approval + merge** by maintainer

### Commit Types

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation update
- `refactor:` - Code refactoring (no functionality change)
- `test:` - Add/update tests
- `chore:` - Maintenance (deps, configs)

**Examples**:
```
feat: add Angeloni supermarket to scraping pipeline
fix: handle empty struct fields in Parquet serialization
docs: update DATA_LAYERS.md with serving layer examples
refactor: simplify VTEXScraper deduplication logic
test: add integration tests for pricing pipeline
```

---

## Testing Guidelines

### DBT Data Tests

**Minimum requirements** for new models:

#### Staging Models (`stg_*`)
- ✅ Not required (ephemeral)

#### Trusted Models (`tru_*`)
- ✅ Primary key: `unique` + `not_null`
- ✅ Foreign keys: `relationships`
- ✅ Business rules: `expression_is_true`
- ✅ Freshness: `recency` check

**Example**:
```yaml
models:
  - name: tru_product
    tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns:
            - product_id
            - region
            - scraped_date
    columns:
      - name: product_id
        tests:
          - not_null
          - unique
      - name: min_price
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 100000
```

📖 **Full guide**: [TESTING_STRATEGY.md](docs/quality/TESTING_STRATEGY.md)

---

## Documentation

### When to Update Docs

- ✅ **New feature**: Update README.md, add section to relevant guide
- ✅ **Architecture change**: Update [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
- ✅ **New data layer**: Update [DATA_LAYERS.md](docs/architecture/DATA_LAYERS.md)
- ✅ **New model**: Add description + column docs in `schema.yml`

### Documentation Standards

1. **Model descriptions** (mandatory):
   ```yaml
   models:
     - name: tru_product
       description: >
         Trusted product model with business logic.
         Deduplicates daily scrapes per product+region.
   ```

2. **Column descriptions** (mandatory for trusted/marts):
   ```yaml
   columns:
     - name: product_id
       description: Unique product identifier from VTEX API
   ```

3. **Meta tags** (mandatory for trusted/marts):
   ```yaml
   config:
     meta:
       graining: product_region_date
       owner: Data Engineering
       contains_pii: false
       main_kpis: min_price, avg_price
   ```

---

## Questions?

- 📧 **Email**: alan.ludke@gmail.com (placeholder)
- 💬 **GitHub Discussions**: [Ask a question](https://github.com/alanludke/market-scraper/discussions)
- 🐛 **Bug report**: [Open an issue](https://github.com/alanludke/market-scraper/issues)

---

## Recognition

Contributors will be:
- ✅ Added to [CONTRIBUTORS.md](CONTRIBUTORS.md)
- ✅ Mentioned in release notes
- ✅ Acknowledged in documentation (if significant contribution)

---

**Thank you for contributing to Market Scraper!** 🙏

Every contribution, no matter how small, makes this project better. We appreciate your time and effort!

---

<div align="center">

[← Back to README](README.md)

</div>
