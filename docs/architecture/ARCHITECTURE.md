# Architecture Overview

High-level architecture of the Market Scraper data platform.

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                               │
│  VTEX APIs (Bistek, Fort, Giassi) → JSON Product Catalogs          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      INGEST LAYER (Python)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  VTEXScraper │  │   Loguru     │  │  Metrics     │             │
│  │  (Parquet)   │  │  (Logs)      │  │  (DuckDB)    │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
│         │                  │                  │                      │
│         ▼                  ▼                  ▼                      │
│  data/bronze/       data/logs/        data/metrics/                 │
│  *.parquet          app.log           runs.duckdb                   │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    TRANSFORM LAYER (DBT)                             │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  STAGING (Ephemeral)                                          │ │
│  │  stg_vtex__products → Union + Standardization                 │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                             │                                        │
│                             ▼                                        │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  TRUSTED (Tables)                                             │ │
│  │  tru_product → Dedup + Flatten + Enrichment                   │ │
│  │  tru_price → Historical pricing time series                   │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                             │                                        │
│                             ▼                                        │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  MARTS (Tables/Incremental)                                   │ │
│  │  fct_prices_daily → Daily price facts                         │ │
│  │  dim_products → Product dimension                             │ │
│  │  dim_stores → Store/region dimension                          │ │
│  └───────────────────────────────────────────────────────────────┘ │
│         │                                                            │
│         ▼                                                            │
│  data/analytics.duckdb (DuckDB OLAP Database)                       │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     ANALYTICS LAYER (Python)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  DuckDB      │  │  Streamlit   │  │  Excel       │             │
│  │  Queries     │  │  Dashboard   │  │  Reports     │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Principles

### 1. **ELT Over ETL**
**Extract → Load → Transform** instead of Extract → Transform → Load.

**Benefits:**
- Raw data preserved in Bronze layer (full history)
- Transformations are declarative SQL (DBT)
- Easy to reprocess and fix errors
- Transparent data lineage

### 2. **Medallion Architecture**
Progressive refinement through layers:

| Layer | Quality | Purpose |
|-------|---------|---------|
| **Bronze (Raw)** | Unprocessed | Exact copy of source data |
| **Silver (Staging)** | Cleaned | Standardized, typed, deduplicated |
| **Gold (Trusted + Marts)** | Refined | Business logic, analytics-ready |

### 3. **Parquet-First**
All data is stored in Apache Parquet format.

**Benefits:**
- 80-90% compression vs JSON
- 35x faster queries than JSONL
- Columnar storage (OLAP-optimized)
- Native support in DuckDB, Pandas, Spark

### 4. **Local-First**
Everything runs locally with zero cloud dependencies.

**Benefits:**
- No recurring cloud costs ($0/month)
- Fast development iteration
- Works offline
- Easy to migrate to cloud later (Azure Blob, S3)

### 5. **Observability Built-In**
Logs, metrics, and data quality tests at every layer.

**Components:**
- **Loguru**: Structured JSON logs with rotation
- **DuckDB**: Metrics database (runs, batches, errors)
- **DBT Tests**: Data quality assertions
- **Great Expectations**: Advanced validation (future)

---

## Technology Stack

### Ingest Layer
| Tool | Purpose | Why |
|------|---------|-----|
| **Python 3.11** | Orchestration | Industry standard, rich ecosystem |
| **Requests** | HTTP client | Robust API interaction |
| **Pandas** | Data manipulation | DataFrame → Parquet conversion |
| **PyArrow** | Parquet I/O | Fast serialization/deserialization |
| **Loguru** | Logging | JSON logs, auto-rotation, structured |

### Transform Layer
| Tool | Purpose | Why |
|------|---------|-----|
| **DBT Core 1.11** | SQL transformations | Declarative, testable, documented |
| **DuckDB 1.10** | OLAP database | Embedded, fast, Parquet-native |
| **dbt-duckdb** | DBT adapter | Connects DBT to DuckDB |

### Analytics Layer
| Tool | Purpose | Why |
|------|---------|-----|
| **DuckDB** | Query engine | OLAP-optimized, SQL interface |
| **Streamlit** | Dashboards | Fast prototyping, Python-based |
| **Pandas** | Data analysis | Rich analytics library |

### Quality & CI/CD
| Tool | Purpose | Why |
|------|---------|-----|
| **sqlfluff** | SQL linting | Code quality, consistency |
| **yamllint** | YAML validation | Catch syntax errors |
| **pre-commit** | Git hooks | Enforce quality before commit |
| **GitHub Actions** | CI/CD | Automated testing, validation |

---

## Data Flow

### 1. Ingestion (Scheduled Daily)

```bash
# Triggered by cron or Prefect (future)
python cli.py scrape --all --parallel

# What happens:
# 1. VTEXScraper hits API endpoints
# 2. JSON responses → DataFrame → Parquet
# 3. Files written to data/bronze/ (partitioned)
# 4. Metrics logged to runs.duckdb
# 5. Logs written to data/logs/app.log
```

**Output:**
```
data/bronze/
├── supermarket=bistek/
│   └── region=florianopolis_costeira/
│       └── year=2026/month=02/day=05/
│           └── run_20260205_143200.parquet
```

### 2. Transformation (On-Demand or Scheduled)

```bash
# Run DBT transformations
cd src/transform/dbt_project
dbt run

# What happens:
# 1. DBT reads bronze Parquet files (external sources)
# 2. Runs staging models (ephemeral CTEs)
# 3. Materializes trusted tables
# 4. Materializes marts tables
# 5. Runs data quality tests
# 6. Writes to data/analytics.duckdb
```

**Output:**
```
data/analytics.duckdb
├── staging.* (ephemeral, not persisted)
├── trusted.tru_product
├── trusted.tru_price
├── pricing_marts.fct_prices_daily
└── pricing_marts.dim_products
```

### 3. Analytics (Interactive)

```bash
# Generate Excel report
python cli_analytics.py report --days 7

# Launch Streamlit dashboard
streamlit run dashboards/pricing_dashboard.py

# Custom SQL query
python cli_analytics.py query "SELECT * FROM fct_prices_daily LIMIT 10"
```

---

## Storage Layout

### Local Development

```
market_scraper/
├── data/                           # All data files (gitignored)
│   ├── bronze/                     # Raw Parquet from scrapers
│   │   ├── supermarket=bistek/
│   │   ├── supermarket=fort/
│   │   └── supermarket=giassi/
│   ├── analytics.duckdb            # DBT output (trusted + marts)
│   ├── metrics/
│   │   └── runs.duckdb             # Scraper metrics
│   └── logs/
│       └── app.log                 # Application logs (JSON)
│
├── src/
│   ├── ingest/                     # Python scrapers
│   ├── transform/dbt_project/      # DBT transformations
│   └── analytics/                  # Queries, reports
│
└── docs/                           # Documentation
```

### Cloud Storage (Future - Azure Blob)

```
stomarketscraper/
├── bronze/
│   └── supermarket=*/region=*/year=*/month=*/day=*/*.parquet
├── silver/
│   └── products/year=*/month=*/day=*/*.parquet
├── gold/
│   ├── fct_prices_daily/month=*/*.parquet
│   └── dim_products/*.parquet
└── metadata/
    ├── runs/runs_*.parquet
    └── quality/quality_reports_*.parquet
```

**Lifecycle Policy:**
- Bronze: 365 days → Cool storage → Archive (2 years)
- Silver/Gold: Keep indefinitely (compressed)
- Metadata: 90 days

---

## Scalability Considerations

### Current Scale (3 Stores, ~30K Products)
- ✅ **Bronze**: ~50MB/day Parquet (vs 500MB JSONL)
- ✅ **Transformations**: <5 seconds (full refresh)
- ✅ **Queries**: <1 second (typical aggregations)
- ✅ **Storage**: ~2GB total (historical data)

### Future Scale (10+ Stores, 100K+ Products)
| Component | Strategy |
|-----------|----------|
| **Ingestion** | Parallel scrapers (asyncio), batching |
| **Bronze** | Daily partitioning, retention policies |
| **Transformations** | Incremental materialization, partition pruning |
| **Query** | Indexed tables, pre-aggregated marts |
| **Storage** | Migrate to Azure Blob + lifecycle policies |
| **Orchestration** | Prefect/Airflow for dependency management |

---

## Security & Privacy

### Data Classification
- ✅ **No PII**: Product pricing data only, no customer info
- ✅ **Public sources**: VTEX e-commerce APIs (public catalogs)
- ✅ **No credentials**: API keys stored in `.env` (gitignored)

### Access Control (Future)
- DBT models have `access_type: public/restricted` metadata
- Implement row-level security in DuckDB or BI layer
- Audit logs for data access

---

## Disaster Recovery

### Backup Strategy
1. **Bronze Layer** (Primary source)
   - Keep 365 days locally
   - Sync to Azure Blob (lifecycle: archive after 90 days)
   - Can always re-scrape if needed

2. **Analytics Database**
   - Daily backup: `cp data/analytics.duckdb backups/`
   - Retention: 30 days
   - Recoverable from Bronze + DBT run

3. **Metrics & Logs**
   - Rotate logs (10MB, 30 days)
   - Export metrics to Parquet monthly
   - Low criticality (operational only)

### Recovery Scenarios
| Scenario | Recovery Time | Data Loss |
|----------|---------------|-----------|
| Lost analytics.duckdb | 5 minutes | 0 (re-run DBT) |
| Lost bronze layer | Hours-Days | Up to 1 day (re-scrape) |
| Code repository lost | Minutes | 0 (Git remote) |

---

## Performance Optimization

### Query Performance
```sql
-- DuckDB auto-optimizes these patterns:

-- 1. Partition pruning (automatic from file paths)
SELECT * FROM bronze_bistek.products
WHERE year = 2026 AND month = 02;

-- 2. Column pruning (Parquet columnar storage)
SELECT product_id, price FROM products;  -- Only reads 2 columns

-- 3. Parallel execution (multi-threaded scans)
SET threads = 8;  -- Use all CPU cores
```

### Transformation Performance
```yaml
# dbt_project.yml
models:
  marts:
    +materialized: incremental
    +on_schema_change: 'append_new_columns'
```

**Incremental processing:**
- Only transform new/changed data
- Use `updated_at` or `loaded_at` watermarks
- 10-100x faster than full refresh

---

## Monitoring & Alerts

### Metrics to Track
| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Data freshness | runs.duckdb | >24h since last run |
| Scrape success rate | runs.duckdb | <95% success |
| Product count anomaly | analytics.duckdb | <80% of average |
| DBT test failures | dbt test | Any failure |
| Storage usage | disk | >80% capacity |

### Observability Dashboard (Future)
Streamlit app showing:
- Last run status per store
- Product count trends
- Price distribution heatmaps
- Data quality test results
- System health metrics

---

## Roadmap

### Phase 2 (Current)
- ✅ Bronze layer (Parquet ingestion)
- ✅ Staging layer (DBT models)
- 🚧 Trusted layer (in progress)
- ⏳ Marts layer (planned)

### Phase 3 (Next 1-3 Months)
- [ ] Complete marts layer (facts + dimensions)
- [ ] Incremental materialization
- [ ] Great Expectations validation
- [ ] Streamlit dashboards

### Phase 4 (3-6 Months)
- [ ] Prefect orchestration
- [ ] Azure Blob sync
- [ ] CI/CD with GitHub Actions
- [ ] Add 5+ more supermarkets

### Phase 5 (6-12 Months)
- [ ] Real-time scraping (streaming)
- [ ] ML price prediction models
- [ ] REST API (FastAPI)
- [ ] Multi-region expansion

---

## References

- [Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture)
- [ELT vs ETL](https://www.integrate.io/blog/elt-vs-etl/)
- [DBT Best Practices](https://docs.getdbt.com/best-practices)
- [DuckDB Performance Guide](https://duckdb.org/docs/guides/performance/how_to_tune_workloads)
