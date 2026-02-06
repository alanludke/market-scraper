# Setup - Market Scraper

Quick setup guide for the Market Scraper data platform.

---

## Prerequisites

- Python 3.11+
- Git
- DuckDB (installed via `pip install duckdb`)
- DBT Core 1.11+ with duckdb adapter

---

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/alanludke/market-scraper
cd market-scraper
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure DBT (Windows Only)

**Windows users need to set UTF-8 encoding for Python:**

#### Option A: PowerShell (Recommended)
Already configured! Just use PowerShell for DBT commands.

If not working, run once:
```powershell
[System.Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'User')
```

Then restart PowerShell.

#### Option B: Git Bash
Add to `~/.bashrc`:
```bash
echo 'export PYTHONUTF8=1' >> ~/.bashrc
```

Restart Git Bash.

---

## Verify Setup

### Test Python

```bash
python --version  # Should be 3.11+
```

### Test DBT

```bash
cd src/transform/dbt_project

# PowerShell (Windows)
dbt debug

# Git Bash (if configured)
dbt debug
```

Expected output: `All checks passed!`

---

## Project Structure

```
market_scraper/
├── src/
│   ├── ingest/          # Python scrapers
│   ├── transform/       # DBT transformations
│   └── analytics/       # Queries, dashboards
├── data/                # All data files (gitignored)
├── docs/                # Project documentation
└── config/              # Configuration files
```

---

## Quick Start

### 1. Run Scrapers

```bash
# Scrape all stores
python cli.py scrape --all --parallel

# Scrape specific store
python cli.py scrape bistek --limit 1000
```

### 2. Run DBT Transformations

```bash
cd src/transform/dbt_project
dbt run
dbt test
```

### 3. Generate Reports

```bash
python cli_analytics.py report --days 7
```

---

## Troubleshooting

### DBT: UnicodeDecodeError on Windows

**Symptom**: `'charmap' codec can't decode byte...`

**Solution**: Configure PYTHONUTF8 (see step 3 above)

### DBT: Cannot open analytics.duckdb

**Symptom**: `IO Error: Cannot open file analytics.duckdb`

**Solution**: Close other connections (Python scripts, DBeaver)

### Scrapers: API Rate Limit

**Symptom**: `429 Too Many Requests`

**Solution**: Wait 60 seconds, scraper auto-retries with backoff

---

## Next Steps

1. Read [CLAUDE.md](./CLAUDE.md) for architecture overview
2. Explore [docs/](./docs/) for detailed documentation
3. Check [Git Flow](./docs/development/GIT_FLOW.md) before contributing

---

## Support

- Issues: https://github.com/alanludke/market-scraper/issues
- Documentation: [docs/](./docs/)
