# Azure Blob Storage - Lakehouse Sync

## Overview

Data lakehouse implementation using Azure Blob Storage with incremental sync, preserving Hive partitioning for analytical queries.

## Architecture

```
stomarketscraper/ (Azure Blob Storage)
├── bronze/                    # Raw Parquet (immutable, append-only)
│   ├── supermarket=angeloni/
│   │   └── region=X/year=Y/month=M/day=D/run_*/
│   ├── supermarket=bistek/
│   └── ...
│
├── analytics/                 # DuckDB databases
│   ├── analytics.duckdb      # Latest (Streamlit Cloud downloads)
│   └── backups/              # Timestamped backups
│       └── analytics_YYYYMMDD_HHMMSS.duckdb
│
└── metadata/                  # Sync tracking (future)
    └── manifests/
```

## Setup

### Prerequisites

```bash
pip install azure-storage-blob python-dotenv
```

### Environment Variables

Add to `.env`:

```env
AZURE_ACCOUNT_NAME="stomarketscraper"
AZURE_ACCOUNT_KEY="your-key-here"
```

## Usage

### CLI Commands

```bash
# Check sync status
python -m scripts.cli sync --layer status

# Sync bronze layer (incremental)
python -m scripts.cli sync --layer bronze

# Sync analytics database
python -m scripts.cli sync --layer analytics

# Full sync (bronze + analytics)
python -m scripts.cli sync --layer all

# Force re-upload everything
python -m scripts.cli sync --force
```

### Python API

```python
from src.storage.azure_blob import LakehouseSync

sync = LakehouseSync()

# Bronze sync (incremental)
stats = sync.sync_bronze()
# Returns: {"uploaded": int, "skipped": int, "errors": int, "total_bytes": int}

# Analytics sync
sas_url = sync.sync_analytics()
# Returns: SAS URL string (valid 1 year)

# Full sync
results = sync.sync_all()

# Check status
status = sync.status()
# Returns: {"local_files": int, "synced_files": int, "pending_files": int, "last_sync": str}
```

## Incremental Sync

### How It Works

1. **Manifest Tracking**: Local file `data/metadata/sync_manifest.json` tracks all synced files
2. **Size-Based Check**: Files are considered synced if path + size match manifest
3. **Checkpoint Saves**: Manifest saved every 50 files and at completion
4. **Idempotent**: Safe to run multiple times, only new/changed files uploaded

### Manifest Structure

```json
{
  "synced_files": {
    "data/bronze/supermarket=bistek/region=floripa/.../file.parquet": {
      "blob_path": "supermarket=bistek/region=floripa/.../file.parquet",
      "size": 1234567,
      "synced_at": "2026-02-07T19:53:58"
    }
  },
  "last_sync": "2026-02-07T19:53:58"
}
```

## Streamlit Cloud Integration

### Initial Setup

1. Run DBT to generate `analytics.duckdb`:
   ```bash
   cd src/transform/dbt_project
   dbt run
   ```

2. Upload to Azure and get SAS URL:
   ```bash
   python -m scripts.cli sync --layer analytics
   ```

3. Copy SAS URL from `azure_analytics_url.txt`

4. Add to Streamlit Cloud secrets:
   - Go to app Settings → Secrets
   - Add:
     ```toml
     db_download_url = "https://stomarketscraper.blob.core.windows.net/analytics/analytics.duckdb?se=..."
     ```

5. App will auto-reboot and download database on first access

### Updates

Whenever you want to update Streamlit Cloud data:

```bash
# 1. Run DBT to update analytics.duckdb
cd src/transform/dbt_project
dbt run

# 2. Upload new version to Azure (auto-generates new SAS URL)
python -m scripts.cli sync --layer analytics

# 3. Update Streamlit secret with new URL from azure_analytics_url.txt
# 4. Reboot Streamlit app
```

**Note**: SAS URL expires after 1 year. Re-run sync to generate new URL.

## Performance

### Bronze Sync Benchmarks

First sync (all files):
- **3,310 files** (707.8 MB)
- **14min 50s**
- **~3.7 files/sec**, **47.6 MB/min**

Subsequent syncs (incremental):
- Only new files uploaded
- Typically **< 1min** for daily scrapes (~100-200 new files)

### Tips

- Run bronze sync **after scraping** completes
- Run analytics sync **after DBT transformations**
- Use `--force` only when manifest is corrupted or structure changed

## Azure Costs

### Storage Tiers

| Tier | Use Case | Cost (per GB/month) |
|------|----------|---------------------|
| Hot | analytics/ (frequent access) | ~$0.018 |
| Cool | bronze/ (infrequent reads, >30 days) | ~$0.010 |
| Archive | bronze/ (rarely accessed, >90 days) | ~$0.002 |

### Cost Estimation

Current setup (~708 MB bronze + 165 MB analytics):
- **Without lifecycle**: ~$0.016/month
- **With lifecycle** (Cool after 30d): ~$0.009/month

**Projected (1 year, daily scrapes):**
- Bronze: ~260 GB → **$2.60/month** (Cool tier)
- Analytics: ~165 MB → **$0.003/month** (Hot tier)
- **Total: ~$2.60/month**

### Lifecycle Policies (Optional)

**Not implemented yet.** To optimize costs:

1. Azure Portal → Storage Account → Lifecycle Management
2. Add rule:
   - **bronze/**: Move to Cool after 30 days, Archive after 90 days
   - **analytics/**: Keep in Hot (frequent access)

## Troubleshooting

### "Container does not exist"

Run sync to auto-create containers:
```bash
python -m scripts.cli sync --layer bronze
```

### "No module named 'src'"

Run from project root:
```bash
cd /path/to/market_scraper
python -m scripts.cli sync --layer status
```

### "Manifest tracking wrong files"

Force re-sync to rebuild manifest:
```bash
python -m scripts.cli sync --layer bronze --force
```

### "Streamlit not showing updated data"

1. Verify DBT ran: `data/analytics.duckdb` timestamp
2. Verify upload succeeded: Check `azure_analytics_url.txt`
3. Verify Streamlit secret matches URL
4. Force reboot Streamlit app
5. Check browser: Clear cache, hard refresh

## Monitoring

### Check Sync Status

```bash
python -m scripts.cli sync --layer status
```

Output:
```
Lakehouse Sync Status
────────────────────────────────────────
Local files:   3,310
Synced:        3,310
Pending:       0
Last sync:     2026-02-07T19:53:58
```

### Azure Portal

1. Storage Account → Containers → bronze/analytics
2. Check blob count, last modified times
3. Monitor storage usage and costs

## Future Enhancements

- [ ] Silver/Gold layer sync (DBT → Azure direct)
- [ ] Lifecycle policies (Cool/Archive automation)
- [ ] Prefect orchestration (scrape → dbt → sync → reboot)
- [ ] DuckDB HTTPFS (read Parquet from Azure, zero download)
- [ ] Metadata container (lineage, quality reports)
- [ ] Multi-region replication
- [ ] Azure Data Lake Gen2 integration

---

**Last Updated**: 2026-02-07
**Implementation**: [src/storage/azure_blob.py](../../src/storage/azure_blob.py)