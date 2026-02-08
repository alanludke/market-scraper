# Project Restructure Plan

## Current Issues

### 1. Files in Root (should be in src/ or scripts/)
- `app.py` → Dashboard entry point (duplicate of `src/dashboard/app.py`)
- `prefect_cloud_runner.py` → Orchestration script
- `run_scraper_standalone.py` → Standalone scraper runner

### 2. Documentation Scattered
- `OPTIMIZATION_GUIDE.md` → Move to `docs/operations/`
- `PREFECT_CLOUD_SETUP.md` → Move to `docs/operations/`
- `STREAMLIT_DEPLOY.md` → Move to `docs/deployment/`
- `SETUP.md` → Keep in root (initial setup)
- `CHANGELOG.md` → Keep in root
- `CONTRIBUTING.md` → Keep in root
- `CONTRIBUTORS.md` → Keep in root

### 3. Junk Files
- `azure_analytics_url.txt` → DELETE
- `reseach.txt` → DELETE (typo in name!)
- `nul` → DELETE (Windows artifact)
- `requirements_dashboard.txt` → DELETE (use `requirements.txt`)

### 4. Legacy Data (11GB JSONL)
- `archive/legacy_scrapers/bistek_products_scraper/` (6.4GB)
- `archive/legacy_scrapers/fort_products_scraper/` (1.7GB)
- `archive/legacy_scrapers/giassi_products_scraper/` (3.3GB)
- `archive/legacy_scrapers/bad_angeloni_products_scraper/` (20KB - corrupted)

**Action**: Migrate to Parquet, then delete archive/

---

## New Structure

```
market_scraper/
├── src/                          # Source code
│   ├── cli/                      # Command-line interfaces
│   │   ├── scraper.py           # Main CLI for scraping (from scripts/cli.py)
│   │   ├── enrichment.py        # EAN enrichment CLI (from scripts/cli_enrich.py)
│   │   ├── validation.py        # Data validation CLI (from scripts/cli_validate_deals.py)
│   │   └── __init__.py
│   │
│   ├── dashboard/                # Streamlit dashboards
│   │   ├── app.py               # Main dashboard (KEEP THIS ONE)
│   │   └── utils/
│   │
│   ├── ingest/                   # Data ingestion
│   │   ├── scrapers/            # Scraper implementations
│   │   └── loaders/             # Data loaders
│   │
│   ├── orchestration/            # Prefect workflows
│   │   ├── scraper_flow.py      # Main scraper flow
│   │   ├── analytics_flow.py    # Analytics flow
│   │   ├── delta_sync_flow.py   # OpenFoodFacts sync
│   │   └── runner.py            # Runner for Prefect Cloud (from prefect_cloud_runner.py)
│   │
│   ├── analytics/                # Analytics engine
│   ├── enrichment/               # Data enrichment
│   ├── observability/            # Logging, metrics
│   ├── schemas/                  # Pydantic models
│   └── transform/                # DBT project
│
├── scripts/                      # Utility scripts
│   ├── deployment/               # Deployment automation
│   │   ├── deploy_to_cloud.sh
│   │   ├── deploy_to_cloud.ps1
│   │   ├── deploy_to_cloud_free_tier.ps1
│   │   ├── start_prefect_server.ps1
│   │   ├── stop_prefect_server.ps1
│   │   └── start_prefect.bat
│   │
│   ├── maintenance/              # Maintenance tasks
│   │   ├── check_old_scraper.py
│   │   ├── check_running_scraper.py
│   │   ├── migrate_legacy_data.py  # NEW: Data migration script
│   │   └── validate_hot_deals_quality.py
│   │
│   ├── monitoring/               # Monitoring tools
│   │   ├── monitor_scrape.py
│   │   └── check_progress.sh
│   │
│   ├── setup/                    # Setup automation
│   │   ├── setup_prefect_cloud_startup.ps1
│   │   ├── setup_startup_task.ps1
│   │   ├── daily_delta_sync.ps1
│   │   ├── daily_delta_sync.bat
│   │   └── install_task_scheduler.ps1
│   │
│   └── azure/                    # Azure utilities
│       ├── upload_analytics_to_azure.py
│       └── update_streamlit.py
│
├── docs/                         # Documentation
│   ├── architecture/
│   ├── development/
│   ├── quality/
│   ├── templates/
│   ├── operations/               # NEW: Operational guides
│   │   ├── OPTIMIZATION_GUIDE.md     # From root
│   │   └── PREFECT_CLOUD_SETUP.md    # From root
│   └── deployment/               # NEW: Deployment guides
│       └── STREAMLIT_DEPLOY.md       # From root
│
├── data/                         # Data storage (gitignored)
│   ├── bronze/
│   ├── silver/
│   ├── gold/
│   ├── logs/
│   └── metrics/
│
├── config/                       # Configuration files
│   └── stores.yaml
│
├── tests/                        # Test suite
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── pages/                        # Streamlit pages (keep for backward compatibility)
│   ├── 1_💰_Análise_de_Preços.py
│   ├── 2_🏷️_Análise_de_Promoções.py
│   └── 3_🥊_Competitividade.py
│
├── .github/                      # GitHub configuration
├── .streamlit/                   # Streamlit config
├── README.md                     # Project overview
├── CLAUDE.md                     # Project instructions
├── SETUP.md                      # Initial setup guide
├── CHANGELOG.md                  # Version history
├── CONTRIBUTING.md               # Contribution guide
├── CONTRIBUTORS.md               # Contributors list
├── LICENSE                       # License
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container definition
├── prefect.yaml                  # Prefect configuration
└── pytest.ini                    # Pytest configuration
```

---

## Migration Steps

### Phase 1: Cleanup Junk
```bash
# Delete junk files
rm azure_analytics_url.txt reseach.txt nul requirements_dashboard.txt
```

### Phase 2: Reorganize Scripts
```bash
# Create new directories
mkdir -p scripts/{deployment,maintenance,monitoring,setup,azure}
mkdir -p src/cli
mkdir -p docs/{operations,deployment}

# Move deployment scripts
mv deploy_to_cloud.sh deploy_to_cloud.ps1 deploy_to_cloud_free_tier.ps1 scripts/deployment/
mv scripts/start_prefect_server.ps1 scripts/stop_prefect_server.ps1 scripts/start_prefect.bat scripts/deployment/

# Move maintenance scripts
mv scripts/check_old_scraper.py scripts/check_running_scraper.py scripts/maintenance/
mv scripts/validate_hot_deals_quality.py scripts/maintenance/

# Move monitoring scripts
mv scripts/monitor_scrape.py scripts/check_progress.sh scripts/monitoring/

# Move setup scripts
mv scripts/setup_prefect_cloud_startup.ps1 scripts/setup_startup_task.ps1 scripts/setup/
mv scripts/daily_delta_sync.ps1 scripts/daily_delta_sync.bat scripts/install_task_scheduler.ps1 scripts/setup/

# Move Azure scripts
mv scripts/upload_analytics_to_azure.py scripts/update_streamlit.py scripts/azure/

# Move CLIs to src/cli/
mv scripts/cli.py src/cli/scraper.py
mv scripts/cli_enrich.py src/cli/enrichment.py
mv scripts/cli_validate_deals.py src/cli/validation.py

# Move investigation script (temporary, can be deleted later)
mv scripts/investigate_carrefour_api.py scripts/maintenance/
```

### Phase 3: Move Root Files
```bash
# Remove duplicate dashboard entry point (keep src/dashboard/app.py)
rm app.py

# Move orchestration files
mv prefect_cloud_runner.py src/orchestration/runner.py
mv run_scraper_standalone.py src/orchestration/standalone_runner.py
```

### Phase 4: Move Documentation
```bash
# Move operational guides
mv OPTIMIZATION_GUIDE.md docs/operations/
mv PREFECT_CLOUD_SETUP.md docs/operations/

# Move deployment guides
mv STREAMLIT_DEPLOY.md docs/deployment/
```

### Phase 5: Migrate Legacy Data
```bash
# Dry run first
python scripts/migrate_legacy_data.py --store all --dry-run

# Actual migration (can take 10-30 minutes)
python scripts/migrate_legacy_data.py --store all

# Validate migrated data
python src/cli/scraper.py validate-bronze --store bistek
python src/cli/scraper.py validate-bronze --store fort
python src/cli/scraper.py validate-bronze --store giassi

# Once validated, delete archive
rm -rf archive/
```

---

## Code Changes Required

### 1. Update imports in all files
- `from scripts.cli import` → `from src.cli.scraper import`
- `from scripts.cli_enrich import` → `from src.cli.enrichment import`

### 2. Update Prefect flows
- `prefect_cloud_runner.py` references → `src.orchestration.runner`

### 3. Update Streamlit config
- `.streamlit/config.toml`: Ensure it points to `src/dashboard/app.py`

### 4. Update GitHub workflows
- `.github/workflows/*`: Update paths if they reference moved files

### 5. Update documentation
- All `docs/*.md`: Update paths to reflect new structure

---

## Validation Checklist

After restructure, validate:

- [ ] All scrapers run: `python src/cli/scraper.py scrape bistek --limit 100`
- [ ] Enrichment works: `python src/cli/enrichment.py stats`
- [ ] Dashboard loads: `streamlit run src/dashboard/app.py`
- [ ] Prefect flows work: `python src/orchestration/runner.py`
- [ ] Tests pass: `pytest tests/`
- [ ] DBT runs: `cd src/transform/dbt_project && dbt run`
- [ ] No broken imports: `python -m py_compile **/*.py`

---

## Benefits

1. **Cleaner root**: Only essential files (README, LICENSE, config)
2. **Logical grouping**: Scripts organized by purpose (deployment, maintenance, monitoring)
3. **Better discoverability**: Clear separation between CLI, orchestration, and dashboard
4. **Smaller footprint**: 11GB archive deleted after migration
5. **Standard structure**: Follows Python project best practices