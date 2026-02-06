<div align="center">

# 🛒 Market Scraper

**Enterprise-grade data platform for supermarket price intelligence**

[![DBT Version](https://img.shields.io/badge/dbt-1.9+-blue.svg)](https://docs.getdbt.com/)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![DuckDB](https://img.shields.io/badge/duckdb-1.1+-yellow.svg)](https://duckdb.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-sqlfluff-brightgreen.svg)](https://sqlfluff.com/)

[Features](#-features) •
[Quick Start](#-quick-start) •
[Architecture](#-architecture) •
[Documentation](#-documentation) •
[Contributing](#-contributing)

</div>

---

## 📋 Overview

**Market Scraper** is a production-ready data platform that collects, transforms, and analyzes product pricing data from supermarket chains in Florianópolis, Brazil. Built with modern data engineering best practices, it provides real-time price intelligence for competitive analysis, market research, and consumer insights.

### Key Highlights

- 🏪 **Multi-Store Coverage**: Bistek, Fort Atacadista, Giassi (37 regions, 30K+ products)
- 📊 **Medallion Architecture**: Bronze → Silver → Gold layers with DBT transformations
- ⚡ **Parquet-First**: 35x faster queries, 600x smaller storage vs JSONL
- 🔄 **Incremental Processing**: 90% time savings with smart watermarking
- 📸 **Historical Tracking**: SCD Type 2 snapshots for price trends
- 🛡️ **Quality Enforced**: Automated linting (SQLFluff), testing (DBT), and CI/CD

---

## 🎯 Features

### Data Collection
- ✅ **Config-driven scrapers** using single `VTEXScraper` class
- ✅ **Regional pricing** with VTEX segment cookies (city-level granularity)
- ✅ **Parallel execution** with thread-safe batching
- ✅ **Auto-retry logic** with exponential backoff
- ✅ **Metadata injection** for lineage tracking

### Data Transformation (DBT)
- ✅ **Layered modeling**: Staging (ephemeral) → Trusted (tables) → Marts (analytics)
- ✅ **Incremental models** with merge/append strategies
- ✅ **Data contracts** enforced via DBT contracts
- ✅ **Snapshots (SCD Type 2)** for historical price analysis
- ✅ **Dimensional modeling** following Kimball methodology

### Analytics & Observability
- ✅ **DuckDB analytics engine** (embedded OLAP, Parquet-native)
- ✅ **Streamlit dashboards** for business + operational metrics
- ✅ **Data quality tests** (uniqueness, freshness, business rules)
- ✅ **Run metadata tracking** in `runs.duckdb`

### Quality & Governance
- ✅ **SQL linting** (SQLFluff with DuckDB dialect)
- ✅ **YAML validation** (yamllint for DBT schemas)
- ✅ **Pre-commit hooks** (15+ automated checks)
- ✅ **CI/CD pipelines** (GitHub Actions on PRs)
- ✅ **Documentation coverage** (100% models + columns)

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Git
- DuckDB (via `pip install duckdb`)
- DBT Core 1.9+ with DuckDB adapter

### Installation

```bash
# 1. Clone repository
git clone https://github.com/alanludke/market-scraper.git
cd market-scraper

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment (Windows only)
# PowerShell (Recommended):
[System.Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'User')
# Restart terminal

# 4. Install DBT packages
cd src/transform/dbt_project
dbt deps
```

### Run Your First Scrape

```bash
# Scrape one store (limited to 1000 products)
python cli.py scrape bistek --limit 1000

# Output: data/bronze/supermarket=bistek/**/*.parquet
```

### Transform with DBT

```bash
cd src/transform/dbt_project

# Parse and validate
dbt parse

# Run transformations
dbt run

# Test data quality
dbt test

# Generate documentation
dbt docs generate
dbt docs serve  # Opens at http://localhost:8080
```

### View Analytics

```bash
# Python CLI (from project root)
python cli.py analytics --days 7

# Or use Streamlit dashboard
streamlit run app.py
```

---

## 🏗️ Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│  VTEX APIs (Bistek, Fort, Giassi)                          │
└────────────────┬────────────────────────────────────────────┘
                 │ Scrape (Python)
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  BRONZE LAYER (Parquet)                                     │
│  Raw data, partitioned by store/region/date                 │
└────────────────┬────────────────────────────────────────────┘
                 │ DBT Transform
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  SILVER LAYER (DBT - Trusted)                               │
│  Deduplication, type casting, business logic                │
└────────────────┬────────────────────────────────────────────┘
                 │ DBT Aggregate
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  GOLD LAYER (DBT - Marts)                                   │
│  Facts & dimensions, analytics-ready                        │
└────────────────┬────────────────────────────────────────────┘
                 │ Query
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  ANALYTICS (DuckDB + Streamlit)                             │
│  Dashboards, reports, price intelligence                    │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer              | Technology          | Purpose                          |
| ------------------ | ------------------- | -------------------------------- |
| **Ingestion**      | Python (requests)   | VTEX API scraping                |
| **Storage**        | Parquet (Snappy)    | Columnar storage (80% compression) |
| **Transformation** | DBT + DuckDB        | SQL-first, incremental ELT       |
| **Analytics**      | DuckDB + Pandas     | OLAP queries, aggregations       |
| **Visualization**  | Streamlit           | Interactive dashboards           |
| **Orchestration**  | Cron / Prefect      | Daily scheduling                 |
| **Quality**        | SQLFluff, yamllint  | Linting, validation              |
| **CI/CD**          | GitHub Actions      | Automated testing on PRs         |

### Data Layers (Medallion Architecture)

| Layer      | Materialization | Purpose                      | Example Model         |
| ---------- | --------------- | ---------------------------- | --------------------- |
| **Raw**    | External        | Unprocessed Parquet files    | `bronze_bistek.products` |
| **Staging** | Ephemeral      | Cast, rename, clean          | `stg_vtex__products`  |
| **Trusted** | Table          | Business logic, dedup        | `tru_product`         |
| **Marts**   | Table/Incremental | Analytics-ready facts/dims | `fct_prices_daily`    |

📖 **Deep dive**: [DATA_LAYERS.md](docs/architecture/DATA_LAYERS.md)

---

## 📚 Documentation

### Getting Started
- 📖 [SETUP.md](SETUP.md) - Installation & configuration guide
- 📖 [src/transform/dbt_project/README.md](src/transform/dbt_project/README.md) - DBT quick reference

### Architecture
- 🏛️ [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) - System design & data flow
- 📊 [DATA_LAYERS.md](docs/architecture/DATA_LAYERS.md) - Medallion architecture (5 layers)
- 📸 [SNAPSHOTS.md](docs/architecture/SNAPSHOTS.md) - Historical tracking (SCD Type 2)
- ⚡ [INCREMENTAL_MODELS.md](docs/architecture/INCREMENTAL_MODELS.md) - Performance optimization

### Templates
- 📋 [EDA_TEMPLATE.md](docs/templates/EDA_TEMPLATE.md) - Exploratory data analysis checklist
- 📈 [KPI_MATRIX.md](docs/templates/KPI_MATRIX.md) - KPI documentation template
- ✅ [PR_CHECKLIST.md](docs/templates/PR_CHECKLIST.md) - Pull request review guide
- 🧩 [KIMBALL_BUS_MATRIX.md](docs/templates/KIMBALL_BUS_MATRIX.md) - Dimensional modeling
- 🗂️ [LOGICAL_DATA_MODEL.md](docs/templates/LOGICAL_DATA_MODEL.md) - ERD template

### Development
- 🌳 [GIT_FLOW.md](docs/development/GIT_FLOW.md) - Branching strategy & workflow
- 🧪 [TESTING_STRATEGY.md](docs/quality/TESTING_STRATEGY.md) - DBT testing guide
- 🛡️ [PROJECT_QUALITY_STANDARDS.md](docs/quality/PROJECT_QUALITY_STANDARDS.md) - Quality enforcement

---

## 🗂️ Project Structure

```
market-scraper/
├── src/
│   ├── ingest/                     # Data extraction
│   │   ├── scrapers/               # VTEXScraper (config-driven)
│   │   └── loaders/                # Parquet writer, Azure uploader
│   ├── transform/                  # DBT project
│   │   └── dbt_project/
│   │       ├── models/             # SQL transformations
│   │       │   ├── staging/        # Ephemeral (stg_*)
│   │       │   ├── trusted/        # Tables (tru_*)
│   │       │   └── marts/          # Facts/Dims (fct_*, dim_*)
│   │       ├── macros/             # Reusable SQL functions
│   │       ├── tests/              # Custom data tests
│   │       ├── .sqlfluff           # SQL linting config
│   │       ├── .yamllint           # YAML validation
│   │       └── .pre-commit-config.yaml  # Git hooks
│   └── analytics/                  # Queries & dashboards
│       └── engine.py               # DuckDB query engine
├── data/                           # All data files (gitignored)
│   ├── bronze/                     # Raw Parquet (scrapers)
│   ├── silver/                     # Cleaned (DBT)
│   ├── gold/                       # Analytics (DBT)
│   ├── logs/                       # Application logs
│   └── metrics/                    # Operational metadata
├── docs/                           # Comprehensive documentation
│   ├── architecture/               # System design
│   ├── templates/                  # Reusable guides
│   ├── development/                # Dev workflows
│   └── quality/                    # Testing & standards
├── .github/
│   └── workflows/                  # CI/CD pipelines
│       ├── lint.yml                # SQL + YAML linting
│       └── test.yml                # DBT tests
├── config/
│   └── stores.yaml                 # Store configurations
├── cli.py                          # Main CLI interface
├── app.py                          # Streamlit dashboard
├── requirements.txt                # Python dependencies
├── CLAUDE.md                       # AI context file
└── README.md                       # You are here!
```

---

## 💻 Usage Examples

### Scraping

```bash
# Scrape all stores (parallel execution)
python cli.py scrape --all --parallel

# Scrape specific store with limit
python cli.py scrape bistek --limit 5000

# Scrape specific region
python cli.py scrape giassi --regions florianopolis_centro

# Verbose output
python cli.py -v scrape fort
```

### DBT Transformations

```bash
cd src/transform/dbt_project

# Run full pipeline
dbt run

# Run specific layer
dbt run --select staging.*
dbt run --select trusted.*
dbt run --select marts.*

# Run incrementally (smart refresh)
dbt run --select +tru_product+  # Model + upstream + downstream

# Run with full refresh
dbt run --full-refresh --select tru_product

# Test data quality
dbt test
dbt test --select tru_product

# Generate lineage docs
dbt docs generate && dbt docs serve
```

### Analytics Queries

```python
# Python API
from src.analytics.engine import AnalyticsEngine

engine = AnalyticsEngine()

# Price comparison
prices = engine.query("""
    SELECT
        supermarket,
        AVG(min_price) as avg_price
    FROM tru_product
    WHERE scraped_date = CURRENT_DATE
    GROUP BY supermarket
""")

# Historical trends (with snapshots)
trends = engine.query("""
    SELECT
        product_name,
        dbt_valid_from as price_date,
        min_price
    FROM snapshots.snap_product_prices
    WHERE product_id = '12345'
    ORDER BY dbt_valid_from DESC
""")
```

---

## 🧪 Testing

### Run All Tests

```bash
# Python unit tests (if implemented)
pytest tests/

# DBT data tests
cd src/transform/dbt_project
dbt test

# SQL linting
sqlfluff lint models/ --dialect duckdb

# YAML validation
yamllint -c .yamllint models/
```

### Pre-commit Hooks

```bash
# Install hooks
cd src/transform/dbt_project
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files

# Run specific hook
pre-commit run sqlfluff-lint
```

### CI/CD

GitHub Actions workflows run automatically on PRs:
- ✅ SQL linting (SQLFluff)
- ✅ YAML validation (yamllint)
- ✅ DBT parsing (`dbt parse`)
- ✅ DBT compilation (`dbt compile`)

---

## 📊 Data Metrics

### Current Coverage (as of 2026-02-05)

| Store          | Regions | Products | Daily Rows | Historical Data |
| -------------- | ------- | -------- | ---------- | --------------- |
| Bistek         | 13      | ~10K     | 130K       | 11GB            |
| Fort Atacadista| 7       | ~10K     | 70K        | 11GB            |
| Giassi         | 17      | ~10K     | 170K       | 11GB            |
| **Total**      | **37**  | **30K**  | **370K**   | **~33GB**       |

### Performance Gains

| Metric              | Before (JSONL) | After (Parquet) | Improvement |
| ------------------- | -------------- | --------------- | ----------- |
| **Storage**         | 11GB           | 18MB            | 600x smaller |
| **Query Time**      | 60s            | 1.7s            | 35x faster  |
| **ETL Duration**    | 50s (full)     | 5s (incremental)| 90% faster  |

---

## 🛠️ Development

### Prerequisites for Contributors

- Python 3.11+
- Git
- DBT Core 1.9+
- SQLFluff (for linting)
- Pre-commit (for hooks)

### Development Workflow

1. **Create feature branch**:
   ```bash
   git checkout -b feature/add-new-store
   ```

2. **Make changes** following [GIT_FLOW.md](docs/development/GIT_FLOW.md)

3. **Run quality checks**:
   ```bash
   cd src/transform/dbt_project
   pre-commit run --all-files
   dbt test
   ```

4. **Create PR** using [PR_CHECKLIST.md](docs/templates/PR_CHECKLIST.md)

5. **Wait for CI/CD** to pass (automated)

6. **Merge** after approval

### Code Standards

- ✅ **SQL**: Lowercase keywords, 4-space indent, leading commas
- ✅ **Python**: PEP 8 (black formatter)
- ✅ **YAML**: 2-space indent, 250 char max line
- ✅ **Naming**: `stg_*`, `tru_*`, `fct_*`, `dim_*` conventions
- ✅ **Documentation**: 100% coverage (models + columns)

📖 **Details**: [PROJECT_QUALITY_STANDARDS.md](docs/quality/PROJECT_QUALITY_STANDARDS.md)

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. **Fork** the repository
2. **Create** a feature branch (`feature/amazing-feature`)
3. **Commit** with clear messages
4. **Push** to your fork
5. **Open** a Pull Request

### Contribution Guidelines

- 📋 Follow the [PR Checklist](docs/templates/PR_CHECKLIST.md)
- 🧪 Add tests for new features
- 📖 Update documentation
- ✅ Ensure CI/CD passes
- 🔍 Request review from maintainers

---

## 📈 Roadmap

### Phase 1: Foundation ✅ (Completed)
- [x] Config-driven VTEX scrapers
- [x] Parquet-first storage
- [x] DBT project setup
- [x] Basic analytics (DuckDB)

### Phase 2: Quality & Testing ✅ (Completed)
- [x] SQLFluff linting
- [x] Pre-commit hooks
- [x] GitHub Actions CI/CD
- [x] Data quality tests

### Phase 3: Advanced Features 🚧 (In Progress)
- [ ] Incremental models (watermarking)
- [ ] Snapshots (SCD Type 2)
- [ ] Dimensional modeling (facts/dims)
- [ ] Streamlit operational dashboard

### Phase 4: Scale & Deploy 🔮 (Planned)
- [ ] Add 10+ stores
- [ ] Prefect orchestration
- [ ] Azure Blob sync
- [ ] Docker containerization

---

## 🐛 Troubleshooting

### Common Issues

#### "DBT cannot open analytics.duckdb"
**Cause**: Database locked by another process.
**Fix**: Close Python scripts, DBeaver, or other connections.

#### "UnicodeDecodeError on Windows"
**Cause**: Missing UTF-8 encoding.
**Fix**: Set `PYTHONUTF8=1` environment variable ([SETUP.md](SETUP.md))

#### "SQLFluff lint failed"
**Cause**: SQL doesn't follow style guide.
**Fix**: Run `sqlfluff fix models/<model>.sql`

📖 **More solutions**: [PROJECT_QUALITY_STANDARDS.md](docs/quality/PROJECT_QUALITY_STANDARDS.md#troubleshooting)

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **DBT** - SQL-first transformation framework
- **DuckDB** - Blazing-fast embedded OLAP
- **SQLFluff** - SQL linting for data teams
- **Kimball Group** - Dimensional modeling methodology
- **VTEX** - E-commerce platform APIs

---

## 📞 Contact

- **Author**: Alan Ludke
- **GitHub**: [@alanludke](https://github.com/alanludke)
- **Project**: [market-scraper](https://github.com/alanludke/market-scraper)

---

<div align="center">

**Made with ❤️ for the data community**

[⭐ Star this repo](https://github.com/alanludke/market-scraper) if you find it useful!

</div>
