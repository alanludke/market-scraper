# DBT Project - Market Scraper Analytics

Transformations layer using DBT (data build tool) for the Market Scraper platform.

## Quick Start

```bash
cd src/transform/dbt_project

# Validate connection
dbt debug

# Run transformations
dbt run

# Test data quality
dbt test

# Generate documentation
dbt docs generate && dbt docs serve
```

**Note**: Windows users should use PowerShell (UTF-8 configured). See [SETUP.md](../../../SETUP.md) for initial configuration.

## Project Structure

```
dbt_project/
├── dbt_project.yml      # Project configuration
├── profiles.yml         # Connection profiles (dev/ci/prod)
├── models/              # SQL models
│   ├── staging/         # Ephemeral staging layer (stg_*)
│   ├── trusted/         # Business logic layer (tru_*)
│   └── marts/           # Analytics layer (fct_*, dim_*)
├── macros/              # Reusable SQL functions
├── tests/               # Custom data tests
└── target/              # Compiled SQL (gitignored)
```

## Layered Architecture

### Staging Layer (`staging/`)
- **Materialization**: Ephemeral (CTE only, no table)
- **Purpose**: Light cleaning, renaming, type casting
- **Naming**: `stg_<source>__<entity>` (e.g., `stg_vtex__products`)
- **No Tests**: Focus on transformation, not validation

### Trusted Layer (`trusted/`)
- **Materialization**: Table (with contracts enforced)
- **Purpose**: Business logic, deduplication, enrichment
- **Naming**: `tru_<entity>` (e.g., `tru_product`, `tru_price`)
- **Tests**: Primary keys, relationships, business rules

### Marts Layer (`marts/`)
- **Materialization**: Table/Incremental (with contracts)
- **Purpose**: Analytics-ready models (facts, dimensions)
- **Naming**: `fct_<process>` (facts) or `dim_<entity>` (dimensions)
- **Tests**: FK relationships, metric validations, aggregations

## Common Commands

### Development Workflow

```bash
# Validate setup
dbt debug

# Parse and validate models
dbt parse

# Compile SQL (preview compiled output)
dbt compile --select stg_vtex__products

# Run models (materialize tables)
dbt run

# Run specific model
dbt run --select tru_product

# Run model and downstream dependencies
dbt run --select tru_product+

# Test data quality
dbt test

# Test specific model
dbt test --select tru_product

# Generate documentation
dbt docs generate
dbt docs serve  # Opens browser at localhost:8080
```

### CI/CD Commands

```bash
# Run only modified models (slim CI)
dbt run --select state:modified+

# Run only failed tests
dbt test --select result:fail

# Fresh data check (validate source freshness)
dbt source freshness
```

## Profiles Configuration

Connection profiles are defined in `profiles.yml`:

- **dev**: Local development (DuckDB at `../../../data/analytics.duckdb`)
- **ci**: CI/CD testing (DuckDB at `../../../data/analytics_ci.duckdb`)
- **prod**: Production (DuckDB at `../../../data/analytics_prod.duckdb`)

Switch targets using:

```bash
# Use default (dev)
dbt run

# Use CI target
dbt run --target ci

# Use prod target
dbt run --target prod
```

## Environment Variables

Configure these for dynamic behavior:

```bash
# Target environment (dev, ci, prod)
set DBT_DEFAULT_TARGET=dev

# DuckDB database path
set DBT_DUCKDB_PATH=../../../data/analytics.duckdb

# Dev schema name (defaults to dev_<username>)
set DEV_SCHEMA_NAME=dev_alan
```

## Troubleshooting

### Error: "Cannot open file analytics.duckdb"
The database file is locked. Close any other connections (Python scripts, DBeaver).

### Error: "UnicodeDecodeError"
Windows: Use PowerShell. See [SETUP.md](../../../SETUP.md) for UTF-8 configuration.

### Warning: "Configuration paths exist... do not apply to any resources"
Normal when you haven't created all models yet. The warning will disappear as you add models.

### Error: "'dbt_utils' is undefined"
Install packages first:
```bash
dbt deps
```

## Documentation

- [Project Docs (Generated)](http://localhost:8080) - Run `dbt docs serve`
- [DBT Core Docs](https://docs.getdbt.com/)
- [DuckDB Adapter Docs](https://docs.getdbt.com/reference/warehouse-setups/duckdb-setup)

## Data Quality

### Running Tests

```bash
# All tests
dbt test

# Specific model
dbt test --select tru_product

# Specific test type
dbt test --select test_type:unique
dbt test --select test_type:not_null
```

### Test Coverage

| Model | Tests | Coverage |
|-------|-------|----------|
| `stg_vtex__products` | 3 | Basic (IDs, nulls) |
| `tru_product` | 8 | High (PK, FK, ranges) |
| `tru_price` | - | TODO |
| `fct_prices_daily` | - | TODO |

## Performance Tips

- Use `--select` to run specific models instead of full project
- Enable incremental materialization for large tables
- Use `threads: 4` in profiles.yml (adjust for your CPU)
- Clean target/ folder periodically: `rm -rf target/`

## Support

For issues or questions:
1. Check [TROUBLESHOOTING.md](../../docs/development/TROUBLESHOOTING.md)
2. Review DBT logs: `logs/dbt.log`
3. Search [DBT Discourse](https://discourse.getdbt.com/)
