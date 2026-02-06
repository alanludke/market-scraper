# Market Scraper - Data Platform

## Overview

Data platform for collecting, transforming, and analyzing supermarket prices in the Florianópolis region. ELT architecture with clear separation between Ingestion, Transformation, and Analytics.

## Architecture

### Principles
1. **Parquet-first**: From bronze onwards, zero JSONL (except logs)
2. **Incremental processing**: DBT watermarking to process only new data
3. **Medallion**: Bronze (raw) → Silver (cleaned) → Gold (aggregated)
4. **Local-first**: Orchestration via cron/Prefect, zero cloud dependencies
5. **Community tools**: Loguru, DBT, Great Expectations (don't reinvent the wheel)

### Layers

**Ingest** (src/ingest/):
- VTEXScraper: API → DataFrame → Parquet (bronze)
- Loguru: Structured logging with correlation IDs
- Metrics: runs.duckdb (operational data)

**Transform** (dbt_market_scraper/):
- DBT models: bronze → silver → gold (incremental SQL)
- Great Expectations: Data quality validation
- Watermarking: Track last processed file

**Analytics** (src/analytics/):
- DuckDB: Query gold/ Parquet files
- Streamlit: Business + operational dashboards

### Stack

| Layer | Tool | Why |
|-------|------|-----|
| Logging | Loguru | Native JSON, automatic rotation |
| Metrics | DuckDB | Already using it, zero extra infra |
| Transform | DBT | SQL-first, incremental, lineage |
| Quality | Great Expectations | Industry standard, free dashboard |
| Orchestration | Cron → Prefect | Zero cost → Automatic retry |
| Storage | Parquet + Azure Blob | 80% compression, medallion in cloud |
| Schemas | Pydantic | Runtime validation, type safety |

## Code Structure

```
src/
├── ingest/          # Extraction (E)
│   ├── scrapers/    # VTEXScraper, BaseScraper
│   └── loaders/     # Parquet writer, Azure uploader
├── transform/       # Transformation (T)
│   └── incremental.py  # Watermarking helpers
└── analytics/       # Load (L)
    └── engine.py    # DuckDB queries

dbt_market_scraper/  # DBT project (transformations)
├── models/
│   ├── bronze/      # Sources (external Parquet)
│   ├── silver/      # Cleaned, deduplicated
│   └── gold/        # Aggregations, business metrics
└── tests/           # DBT data tests
```

## Useful Commands

### Ingestion
```bash
# Scrape single store
python cli_ingest.py scrape bistek --limit 1000

# Scrape all stores
python cli_ingest.py scrape --all

# Check health
python cli_ingest.py health
```

### Transformation (DBT)
```bash
# Run all models
cd dbt_market_scraper && dbt run

# Run specific layer
dbt run --select silver.*
dbt run --select gold.*

# Run incrementally (only new data)
dbt run --select silver.products  # Uses watermarking

# Test data quality
dbt test

# Generate docs
dbt docs generate && dbt docs serve
```

### Data Quality (Great Expectations)
```bash
# Run checkpoint
great_expectations checkpoint run bronze_checkpoint

# Open Data Docs dashboard
open great_expectations/uncommitted/data_docs/index.html
```

### Analytics
```bash
# Generate Excel report
python cli_analytics.py report --days 7

# Run custom query
python cli_analytics.py query "SELECT * FROM gold.price_index LIMIT 10"
```

### Sync to Azure
```bash
# Upload bronze/silver/gold to Azure Blob
python cli_sync.py upload --layer all

# Upload specific layer
python cli_sync.py upload --layer gold
```

## Code Patterns

### Logging (Loguru)
```python
from loguru import logger

# Bind context for correlation IDs
logger = logger.bind(run_id=run_id, store="bistek", region="florianopolis")
logger.info("Starting scrape", products_count=1234)

# Exception logging (automatic)
try:
    scrape()
except Exception as e:
    logger.exception("Scrape failed")  # Log full traceback
```

### Schemas (Pydantic)
```python
from src.schemas.vtex import VTEXProduct

# Validate API response
try:
    product = VTEXProduct.parse_obj(api_response)
except ValidationError as e:
    logger.error("Invalid product schema", error=str(e))
    metrics.increment("validation_errors")
```

### Metrics
```python
from src.observability.metrics import MetricsCollector

metrics = MetricsCollector()
metrics.start_run(run_id, store_name, region_key)

# Track batch
with metrics.track_batch(batch_number) as batch:
    products = scrape_batch()
    batch.products_count = len(products)

metrics.finish_run(status="success", products_scraped=total)
```

## Architectural Decisions (ADRs)

### ADR-001: Why Parquet (not JSONL)?
- **Performance**: 35x faster (1.7s vs 60s queries)
- **Storage**: 600x smaller (18MB vs 11GB)
- **Ecosystem**: DuckDB, DBT, Pandas read natively
- **Columnar**: Ideal for analytical aggregations

### ADR-002: Why DBT (not Python scripts)?
- **SQL-first**: Declarative transformations, easy maintenance
- **Incremental**: Automatic watermarking with `is_incremental()`
- **Lineage**: Visual DAG of dependencies
- **Testing**: dbt test validates data quality
- **Docs**: Auto-generated data catalog

### ADR-003: Why DuckDB (not PostgreSQL)?
- **OLAP**: Optimized for analytical aggregations
- **Embedded**: Zero infrastructure, local file
- **Parquet native**: Direct queries on Parquet files
- **Cost**: Free, no limits

### ADR-004: Why Loguru (not stdlib logging)?
- **Native JSON**: `.add(serialize=True)` automatic
- **Auto rotation**: `.add(rotation="10 MB")`
- **Clean syntax**: Less boilerplate
- **Context binding**: `.bind(key=value)` thread-safe

### ADR-005: Why Great Expectations (not custom checks)?
- **Community standard**: Industry standard
- **Declarative**: Expectations in YAML
- **Free dashboard**: Data Docs HTML
- **DBT integration**: great_expectations_dbt plugin

## Data Layout (Azure Blob)

```
stomarketscraper/
├── bronze/
│   └── supermarket=bistek/region=florianopolis_costeira/
│       └── year=2026/month=02/day=05/
│           └── run_20260205_143200.parquet
├── silver/
│   ├── products/year=2026/month=02/day=05/*.parquet
│   └── prices/year=2026/month=02/day=05/*.parquet
├── gold/
│   ├── price_index/month=2026-02/*.parquet
│   └── competitiveness/month=2026-02/*.parquet
└── metadata/
    ├── runs/runs_2026_02.parquet
    └── quality/quality_reports_2026_02.parquet
```

## Observability

### Logs
- **Location**: `data/logs/app.log` (JSON, rotating 10MB, 30 days)
- **Query**: DuckDB can read: `SELECT * FROM read_json_auto('data/logs/app.log')`

### Metrics
- **Location**: `data/metrics/runs.duckdb`
- **Tables**: `scraper_runs`, `scraper_batches`
- **Retention**: Indefinite (fast queries in DuckDB)

### Data Quality
- **Location**: `great_expectations/uncommitted/data_docs/`
- **Access**: `open great_expectations/uncommitted/data_docs/index.html`

### Alerts
- **Location**: `data/alerts/active_alerts.json`
- **Check**: `python cli_analytics.py check-alerts`

## Legacy Data

**Warning**: Corrupted data and old scrapers have been archived:

- `data/archive/bad_angeloni_products_scraper/` - Corrupted JSONL (do not use!)
- `archive/legacy_scrapers/` - Old scrapers (bistek, fort, giassi) - replaced by unified VTEXScraper

**Analytics**: Automatic filters exclude `data/archive/` and `bad_*` paths.

## Future Roadmap

### Short Term (1-3 months)
- [ ] Prefect orchestration (replace cron)
- [ ] Multi-stage Docker (ingest, transform, dashboard)
- [ ] E2E tests (pytest with 80%+ coverage)

### Medium Term (3-6 months)
- [ ] Add more stores (10+ supermarkets)
- [ ] Real-time scraping (streaming vs batch)
- [ ] REST API (FastAPI serving gold layer)

### Long Term (6-12 months)
- [ ] Terraform (IaC for Azure resources)
- [ ] Airflow/Dagster (if advanced orchestration needed)
- [ ] ML models (price prediction, anomaly detection)

## Cost Optimization

**Target**: $0-10/month (Azure storage only)

Strategies:
- ✅ Local execution (cron/Prefect local, not cloud VMs)
- ✅ Parquet compression (reduces storage 80-90%)
- ✅ Lifecycle policies (Cool → Archive after 30/90 days)
- ✅ Retention (delete data > 1 year)
- ✅ Incremental processing (don't reprocess everything always)

## Documentation

The project has comprehensive documentation in `docs/`:

### Development
- **[GIT_FLOW.md](docs/development/GIT_FLOW.md)**: Trunk-based workflow, branch conventions, PR template
- **[TESTING_STRATEGY.md](docs/quality/TESTING_STRATEGY.md)**: DBT testing strategy by layer (staging, trusted, marts)

### Architecture
- **[ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)**: ELT architecture overview, tech stack, data flow
- **[DATA_LAYERS.md](docs/architecture/DATA_LAYERS.md)**: Complete Medallion architecture guide (5 layers: Raw → Staging → Trusted → Marts → Serving)
- **[SNAPSHOTS.md](docs/architecture/SNAPSHOTS.md)**: Complete DBT snapshots guide (SCD Type 2) for price history
- **[INCREMENTAL_MODELS.md](docs/architecture/INCREMENTAL_MODELS.md)**: Incremental strategies (merge, append, watermarking)

### Templates
- **[EDA_TEMPLATE.md](docs/templates/EDA_TEMPLATE.md)**: 10-section checklist for adding new data source
- **[KPI_MATRIX.md](docs/templates/KPI_MATRIX.md)**: Template for documenting KPIs and implementation (pricing, catalog, operational)
- **[PR_CHECKLIST.md](docs/templates/PR_CHECKLIST.md)**: Complete PR checklist (testing, data quality, documentation, schema)
- **[KIMBALL_BUS_MATRIX.md](docs/templates/KIMBALL_BUS_MATRIX.md)**: Bus Matrix template for conformed dimensions (dimensional modeling)
- **[LOGICAL_DATA_MODEL.md](docs/templates/LOGICAL_DATA_MODEL.md)**: Logical data model template with ERD (Entity-Relationship Diagram)

### Quality
- **[TESTING_STRATEGY.md](docs/quality/TESTING_STRATEGY.md)**: DBT testing strategy by layer (staging, trusted, marts)
- **[PROJECT_QUALITY_STANDARDS.md](docs/quality/PROJECT_QUALITY_STANDARDS.md)**: Quality standards (linting, validation, CI/CD enforcement)

### Setup
- **[SETUP.md](SETUP.md)**: Initial configuration guide (Windows UTF-8, DBT, DuckDB)
- **[src/transform/dbt_project/README.md](src/transform/dbt_project/README.md)**: Quick reference for DBT commands

## Quality Assurance

### Linting & Formatting
```bash
# SQL linting with SQLFluff (DuckDB dialect)
cd src/transform/dbt_project
sqlfluff lint models/ --dialect duckdb

# Auto-fix SQL issues
sqlfluff fix models/ --dialect duckdb

# YAML linting
yamllint -c .yamllint models/
```

**Configs**:
- `.sqlfluff`: SQLFluff config for DuckDB + DBT templater
- `.yamllint`: YAML linting rules for DBT schemas

### Pre-commit Hooks
```bash
# Install pre-commit
pip install pre-commit

# Install hooks
cd src/transform/dbt_project
pre-commit install

# Run manually
pre-commit run --all-files
```

**Configured hooks** (`.pre-commit-config.yaml`):
- ✅ `dbt-parse`: Validates DBT project compiles
- ✅ `check-script-semicolon`: Prohibits semicolons in SQL
- ✅ `check-model-columns-have-desc`: Requires column descriptions (trusted/marts)
- ✅ `check-model-has-description`: Requires model descriptions
- ✅ `check-model-has-meta-keys`: Validates mandatory metadata (graining, owner, contains_pii)
- ✅ `check-model-name-contract`: Validates naming conventions (stg_*, tru_*, fct_*, dim_*)
- ✅ `sqlfluff-lint`: Lint SQL with SQLFluff
- ✅ `yamllint`: Lint YAML schemas

### CI/CD (GitHub Actions)
**Workflows**:
- **[.github/workflows/lint.yml](.github/workflows/lint.yml)**: Runs SQLFluff + YAML lint on PRs
- **[.github/workflows/test.yml](.github/workflows/test.yml)**: Runs `dbt parse` and `dbt compile` on PRs

```bash
# Automatic triggers:
# - PRs to main/master
# - Modifications in src/transform/dbt_project/**

# Manual execution:
gh workflow run lint.yml
gh workflow run test.yml
```

## Troubleshooting

### "Scraper failed without logs"
- Check: `data/logs/app.log` (JSON with exceptions)
- Check: `data/metrics/runs.duckdb` (run status)
- Solution: Loguru captures everything, if no logs = scraper didn't start

### "DBT model failed"
- Run: `dbt run --select <model> --debug`
- Check: `logs/dbt.log`
- Common: Schema change (use `on_schema_change='append_new_columns'`)

### "Great Expectations validation failed"
- Open: `great_expectations/uncommitted/data_docs/`
- Fix: Update expectations or fix bronze data
- Re-run: `great_expectations checkpoint run bronze_checkpoint`

### "DuckDB query slow"
- Check: Querying JSONL? (Migrate to Parquet!)
- Check: WHERE filter without index? (DuckDB has no indexes)
- Solution: Partition pruning (filter by year/month/day)

## Useful Links

- **GitHub Project**: https://github.com/alanludke/market-scraper (private)
- **DBT Docs**: https://docs.getdbt.com/
- **Great Expectations Docs**: https://docs.greatexpectations.io/
- **Loguru Docs**: https://loguru.readthedocs.io/
- **DuckDB Docs**: https://duckdb.org/docs/

---

**Last updated**: 2026-02-05
**Version**: 2.0 (complete refactor with ELT architecture)
