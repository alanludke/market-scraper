# DBT Project - Market Scraper Analytics

Transformations layer using DBT (data build tool) for the Market Scraper platform.

## Quick Start

### Using the DBT Wrapper (Recommended)

To avoid encoding issues on Windows, use the provided wrapper scripts:

**Command Prompt / Git Bash:**
```bash
cd src/transform/dbt_project
./dbt.bat debug
./dbt.bat parse
./dbt.bat run
./dbt.bat test
```

**PowerShell:**
```powershell
cd src\transform\dbt_project
.\dbt.ps1 debug
.\dbt.ps1 parse
.\dbt.ps1 run
.\dbt.ps1 test
```

The wrappers automatically set `PYTHONUTF8=1` so you don't need to prefix every command.

### Using DBT Directly

If you prefer to use `dbt` directly:

**Windows (Command Prompt):**
```cmd
set PYTHONUTF8=1
dbt debug
```

**Linux/Mac:**
```bash
export PYTHONUTF8=1
dbt debug
```

## Project Structure

```
dbt_project/
├── dbt.bat              # Windows wrapper script
├── dbt.ps1              # PowerShell wrapper script
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
./dbt.bat debug

# Parse and validate models
./dbt.bat parse

# Compile SQL (preview compiled output)
./dbt.bat compile --select stg_vtex__products

# Run models (materialize tables)
./dbt.bat run

# Run specific model
./dbt.bat run --select tru_product

# Run model and downstream dependencies
./dbt.bat run --select tru_product+

# Test data quality
./dbt.bat test

# Test specific model
./dbt.bat test --select tru_product

# Generate documentation
./dbt.bat docs generate
./dbt.bat docs serve  # Opens browser at localhost:8080
```

### CI/CD Commands

```bash
# Run only modified models (slim CI)
./dbt.bat run --select state:modified+

# Run only failed tests
./dbt.bat test --select result:fail

# Fresh data check (validate source freshness)
./dbt.bat source freshness
```

## Profiles Configuration

Connection profiles are defined in `profiles.yml`:

- **dev**: Local development (DuckDB at `../../../data/analytics.duckdb`)
- **ci**: CI/CD testing (DuckDB at `../../../data/analytics_ci.duckdb`)
- **prod**: Production (DuckDB at `../../../data/analytics_prod.duckdb`)

Switch targets using:

```bash
# Use default (dev)
./dbt.bat run

# Use CI target
./dbt.bat run --target ci

# Use prod target
./dbt.bat run --target prod
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
Use the wrapper scripts (`dbt.bat` or `dbt.ps1`) or set `PYTHONUTF8=1` manually.

### Warning: "Configuration paths exist... do not apply to any resources"
Normal when you haven't created all models yet. The warning will disappear as you add models.

### Error: "'dbt_utils' is undefined"
Install packages first:
```bash
./dbt.bat deps
```

## Documentation

- [Project Docs (Generated)](http://localhost:8080) - Run `./dbt.bat docs serve`
- [DBT Core Docs](https://docs.getdbt.com/)
- [DuckDB Adapter Docs](https://docs.getdbt.com/reference/warehouse-setups/duckdb-setup)

## Data Quality

### Running Tests

```bash
# All tests
./dbt.bat test

# Specific model
./dbt.bat test --select tru_product

# Specific test type
./dbt.bat test --select test_type:unique
./dbt.bat test --select test_type:not_null
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
