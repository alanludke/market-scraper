# Market Scraper - Data Platform

## Visão Geral

Plataforma de dados para coleta, transformação e análise de preços de supermercados na região de Florianópolis. Arquitetura ELT com separação clara entre Ingestão, Transformação e Analytics.

## Arquitetura

### Princípios
1. **Parquet-first**: Desde bronze, zero JSONL (exceto logs)
2. **Incremental processing**: Watermarking DBT para processar apenas novos dados
3. **Medallion**: Bronze (raw) → Silver (cleaned) → Gold (aggregated)
4. **Local-first**: Orquestração via cron/Prefect, zero cloud dependencies
5. **Community tools**: Loguru, DBT, Great Expectations (não reinventar a roda)

### Camadas

**Ingest** (src/ingest/):
- VTEXScraper: API → DataFrame → Parquet (bronze)
- Loguru: Structured logging com correlation IDs
- Metrics: runs.duckdb (operational data)

**Transform** (dbt_market_scraper/):
- DBT models: bronze → silver → gold (SQL incremental)
- Great Expectations: Data quality validation
- Watermarking: Track last processed file

**Analytics** (src/analytics/):
- DuckDB: Query gold/ Parquet files
- Streamlit: Business + operational dashboards

### Stack

| Layer | Tool | Why |
|-------|------|-----|
| Logging | Loguru | JSON nativo, rotation automática |
| Metrics | DuckDB | Já usamos, zero infra extra |
| Transform | DBT | SQL-first, incremental, lineage |
| Quality | Great Expectations | Padrão indústria, dashboard grátis |
| Orchestration | Cron → Prefect | Zero custo → Retry automático |
| Storage | Parquet + Azure Blob | 80% compression, medallion na cloud |
| Schemas | Pydantic | Runtime validation, type safety |

## Estrutura de Código

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

## Comandos Úteis

### Ingestão
```bash
# Scrape single store
python cli_ingest.py scrape bistek --limit 1000

# Scrape all stores
python cli_ingest.py scrape --all

# Check health
python cli_ingest.py health
```

### Transformação (DBT)
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

## Padrões de Código

### Logging (Loguru)
```python
from loguru import logger

# Bind context para correlation IDs
logger = logger.bind(run_id=run_id, store="bistek", region="florianopolis")
logger.info("Starting scrape", products_count=1234)

# Exception logging (automático)
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

## Decisões Arquiteturais (ADRs)

### ADR-001: Por que Parquet (não JSONL)?
- **Performance**: 35x mais rápido (1.7s vs 60s queries)
- **Storage**: 600x menor (18MB vs 11GB)
- **Ecosystem**: DuckDB, DBT, Pandas leem nativamente
- **Columnar**: Ideal para agregações analíticas

### ADR-002: Por que DBT (não Python scripts)?
- **SQL-first**: Transformações declarativas, fácil manutenção
- **Incremental**: Watermarking automático com `is_incremental()`
- **Lineage**: DAG visual de dependências
- **Testing**: dbt test valida data quality
- **Docs**: Catálogo de dados auto-gerado

### ADR-003: Por que DuckDB (não PostgreSQL)?
- **OLAP**: Otimizado para agregações analíticas
- **Embedded**: Zero infraestrutura, arquivo local
- **Parquet nativo**: Queries diretos em Parquet files
- **Cost**: Gratuito, sem limites

### ADR-004: Por que Loguru (não stdlib logging)?
- **JSON nativo**: `.add(serialize=True)` automático
- **Rotation automática**: `.add(rotation="10 MB")`
- **Syntax limpa**: Menos boilerplate
- **Context binding**: `.bind(key=value)` thread-safe

### ADR-005: Por que Great Expectations (não custom checks)?
- **Community standard**: Padrão da indústria
- **Declarativo**: Expectations em YAML
- **Dashboard grátis**: Data Docs HTML
- **Integração DBT**: great_expectations_dbt plugin

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

## Observabilidade

### Logs
- **Location**: `data/logs/app.log` (JSON, rotating 10MB, 30 dias)
- **Query**: DuckDB pode ler: `SELECT * FROM read_json_auto('data/logs/app.log')`

### Metrics
- **Location**: `data/metrics/runs.duckdb`
- **Tables**: `scraper_runs`, `scraper_batches`
- **Retention**: Indefinido (queries rápidas em DuckDB)

### Data Quality
- **Location**: `great_expectations/uncommitted/data_docs/`
- **Access**: `open great_expectations/uncommitted/data_docs/index.html`

### Alerts
- **Location**: `data/alerts/active_alerts.json`
- **Check**: `python cli_analytics.py check-alerts`

## Legacy Data

**Atenção**: Dados corrompidos e scrapers antigos foram arquivados:

- `data/archive/bad_angeloni_products_scraper/` - Corrupted JSONL (não usar!)
- `archive/legacy_scrapers/` - Scrapers antigos (bistek, fort, giassi) - substituídos por VTEXScraper unificado

**Analytics**: Filtros automáticos excluem `data/archive/` e `bad_*` paths.

## Roadmap Futuro

### Curto Prazo (1-3 meses)
- [ ] Prefect orchestration (substituir cron)
- [ ] Docker multi-stage (ingest, transform, dashboard)
- [ ] Testes E2E (pytest com cobertura 80%+)

### Médio Prazo (3-6 meses)
- [ ] Adicionar mais stores (10+ supermercados)
- [ ] Real-time scraping (streaming vs batch)
- [ ] API REST (FastAPI servindo gold layer)

### Longo Prazo (6-12 meses)
- [ ] Terraform (IaC para Azure resources)
- [ ] Airflow/Dagster (se precisar orquestração avançada)
- [ ] ML models (price prediction, anomaly detection)

## Cost Optimization

**Target**: $0-10/mês (apenas Azure storage)

Estratégias:
- ✅ Local execution (cron/Prefect local, não cloud VMs)
- ✅ Parquet compression (reduz storage 80-90%)
- ✅ Lifecycle policies (Cool → Archive após 30/90 dias)
- ✅ Retention (deletar dados > 1 ano)
- ✅ Incremental processing (não reprocessar tudo sempre)

## Documentação

O projeto possui documentação abrangente em `docs/`:

### Development
- **[GIT_FLOW.md](docs/development/GIT_FLOW.md)**: Workflow trunk-based, convenções de branch, PR template
- **[TESTING_STRATEGY.md](docs/quality/TESTING_STRATEGY.md)**: Estratégia de testes DBT por camada (staging, trusted, marts)

### Architecture
- **[ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)**: Visão geral da arquitetura ELT, stack tecnológico, data flow
- **[DATA_LAYERS.md](docs/architecture/DATA_LAYERS.md)**: Guia completo da arquitetura Medallion (5 camadas: Raw → Staging → Trusted → Marts → Serving)
- **[SNAPSHOTS.md](docs/architecture/SNAPSHOTS.md)**: Guia completo de DBT snapshots (SCD Type 2) para histórico de preços
- **[INCREMENTAL_MODELS.md](docs/architecture/INCREMENTAL_MODELS.md)**: Estratégias incrementais (merge, append, watermarking)

### Templates
- **[EDA_TEMPLATE.md](docs/templates/EDA_TEMPLATE.md)**: Checklist de 10 seções para adicionar nova fonte de dados
- **[KPI_MATRIX.md](docs/templates/KPI_MATRIX.md)**: Template para documentar KPIs e implementação (pricing, catalog, operational)
- **[PR_CHECKLIST.md](docs/templates/PR_CHECKLIST.md)**: Checklist completo para PRs (testing, data quality, documentation, schema)
- **[KIMBALL_BUS_MATRIX.md](docs/templates/KIMBALL_BUS_MATRIX.md)**: Template de Bus Matrix para dimensões conformadas (dimensional modeling)
- **[LOGICAL_DATA_MODEL.md](docs/templates/LOGICAL_DATA_MODEL.md)**: Template de modelo lógico de dados com ERD (Entity-Relationship Diagram)

### Quality
- **[TESTING_STRATEGY.md](docs/quality/TESTING_STRATEGY.md)**: Estratégia de testes DBT por camada (staging, trusted, marts)
- **[PROJECT_QUALITY_STANDARDS.md](docs/quality/PROJECT_QUALITY_STANDARDS.md)**: Padrões de qualidade (linting, validation, CI/CD enforcement)

### Setup
- **[SETUP.md](SETUP.md)**: Guia de configuração inicial (Windows UTF-8, DBT, DuckDB)
- **[src/transform/dbt_project/README.md](src/transform/dbt_project/README.md)**: Referência rápida de comandos DBT

## Quality Assurance

### Linting & Formatting
```bash
# SQL linting com SQLFluff (DuckDB dialect)
cd src/transform/dbt_project
sqlfluff lint models/ --dialect duckdb

# Auto-fix SQL issues
sqlfluff fix models/ --dialect duckdb

# YAML linting
yamllint -c .yamllint models/
```

**Configs**:
- `.sqlfluff`: SQLFluff config para DuckDB + DBT templater
- `.yamllint`: YAML linting rules para DBT schemas

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

**Hooks configurados** (`.pre-commit-config.yaml`):
- ✅ `dbt-parse`: Valida projeto DBT compila
- ✅ `check-script-semicolon`: Proíbe semicolons em SQL
- ✅ `check-model-columns-have-desc`: Exige descrição de colunas (trusted/marts)
- ✅ `check-model-has-description`: Exige descrição de modelos
- ✅ `check-model-has-meta-keys`: Valida metadados obrigatórios (graining, owner, contains_pii)
- ✅ `check-model-name-contract`: Valida naming conventions (stg_*, tru_*, fct_*, dim_*)
- ✅ `sqlfluff-lint`: Lint SQL com SQLFluff
- ✅ `yamllint`: Lint YAML schemas

### CI/CD (GitHub Actions)
**Workflows**:
- **[.github/workflows/lint.yml](.github/workflows/lint.yml)**: Roda SQLFluff + YAML lint em PRs
- **[.github/workflows/test.yml](.github/workflows/test.yml)**: Roda `dbt parse` e `dbt compile` em PRs

```bash
# Triggers automáticos:
# - PRs para main/master
# - Modificações em src/transform/dbt_project/**

# Execução manual:
gh workflow run lint.yml
gh workflow run test.yml
```

## Troubleshooting

### "Scraper falhou sem logs"
- Check: `data/logs/app.log` (JSON com exceptions)
- Check: `data/metrics/runs.duckdb` (status do run)
- Solution: Loguru captura tudo, se não tem log = scraper não iniciou

### "DBT model failed"
- Run: `dbt run --select <model> --debug`
- Check: `logs/dbt.log`
- Common: Schema change (use `on_schema_change='append_new_columns'`)

### "Great Expectations validation failed"
- Open: `great_expectations/uncommitted/data_docs/`
- Fix: Atualizar expectations ou corrigir dados bronze
- Re-run: `great_expectations checkpoint run bronze_checkpoint`

### "DuckDB query slow"
- Check: Está querying JSONL? (Migrar para Parquet!)
- Check: Filtro WHERE sem índice? (DuckDB não tem índices)
- Solution: Partition pruning (filtrar por year/month/day)

## Links Úteis

- **Projeto GitHub**: https://github.com/alanludke/market-scraper (private)
- **DBT Docs**: https://docs.getdbt.com/
- **Great Expectations Docs**: https://docs.greatexpectations.io/
- **Loguru Docs**: https://loguru.readthedocs.io/
- **DuckDB Docs**: https://duckdb.org/docs/

---

**Última atualização**: 2026-02-05
**Versão**: 2.0 (refactor completo com ELT architecture)
