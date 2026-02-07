# Streamlit Cloud - Auto-Update System

## Overview

Automated system for keeping Streamlit Cloud dashboard synchronized with latest data from Azure Blob Storage, with intelligent cache invalidation.

## How It Works

### Smart Cache Invalidation

The dashboard automatically detects when new data is available:

```python
# src/dashboard/utils/db_manager.py

1. Checks if SAS URL changed (compares with cached URL)
2. If changed → Deletes old database → Downloads new version
3. If unchanged → Uses cached database (fast load)
4. Caches URL after successful download
```

### URL Comparison Logic

```
Current URL (from Streamlit secrets)
    ↓
Compare with cached URL (data/.db_url_cache)
    ↓
If different:
  - Delete data/analytics.duckdb
  - Download from new URL
  - Cache new URL
    ↓
If same:
  - Use existing database
  - Skip download
```

## Update Workflow

### Automated Pipeline Script

```bash
# Complete flow: DBT → Azure → Instructions
python scripts/update_streamlit.py

# Options:
python scripts/update_streamlit.py --skip-dbt     # Skip DBT (already ran)
python scripts/update_streamlit.py --dbt-only     # Only run DBT
```

### Manual Steps

1. **Run DBT** (transform new data):
   ```bash
   cd src/transform/dbt_project
   dbt run
   ```

2. **Upload to Azure** (get new SAS URL):
   ```bash
   python -m scripts.cli sync --layer analytics
   ```

3. **Update Streamlit Secret**:
   - Copy URL from `azure_analytics_url.txt`
   - Streamlit Cloud → Settings → Secrets
   - Replace `db_download_url` with new URL
   - Save (app auto-reboots)

4. **Verify Update**:
   - Access dashboard
   - Should show: "🔄 New database version detected. Downloading updated data..."
   - Wait ~2 minutes for download (165 MB)
   - Verify latest data appears

## File Structure

```
data/
├── analytics.duckdb          # Main database (165 MB)
└── .db_url_cache            # Cached SAS URL (for comparison)
```

**Note**: Both files are ephemeral on Streamlit Cloud (recreated on reboot).

## Timeline

| Event | Duration | What Happens |
|-------|----------|-------------|
| Upload to Azure | ~4 min | New `analytics.duckdb` uploaded, new SAS URL generated |
| Update Streamlit secret | ~30 sec | Paste new URL, save |
| App reboot | ~1 min | Streamlit Cloud restarts with new secret |
| URL comparison | <1 sec | Detects URL changed, deletes old DB |
| Download new DB | ~2 min | Downloads 165 MB from Azure |
| **Total** | **~8 min** | From upload to updated dashboard |

## Troubleshooting

### "Still showing old data"

**Cause**: Secret not updated or app didn't reboot.

**Solution**:
1. Verify secret has **latest URL** from `azure_analytics_url.txt`
2. Manual reboot: Settings → Reboot app
3. Clear browser cache (Ctrl+Shift+R)

### "Database not downloading"

**Cause**: URL comparison failed or cache file corrupted.

**Solution**:
1. Delete `data/.db_url_cache` manually (if accessible)
2. Reboot app (will trigger fresh download)
3. Check Streamlit logs for errors

### "Download failed / partial file"

**Cause**: Network error during download.

**Solution**:
- Streamlit automatically deletes partial files (line 93 of db_manager.py)
- Reboot app to retry download
- Check Azure Blob accessibility (SAS URL not expired)

### "Database size wrong"

**Cause**: Old database still cached.

**Solution**:
1. Verify `azure_analytics_url.txt` has **newest URL**
2. Check URL expiry date in SAS token (`se=` parameter)
3. Generate fresh URL if expired:
   ```bash
   python -m scripts.cli sync --layer analytics
   ```

## Monitoring

### Expected Indicators

When update is working correctly:

```
🔄 New database version detected. Downloading updated data...
📥 Downloading database...
[Progress bar: 0% → 100%]
✅ Database downloaded: 165.5 MB
```

### Database Info

The dashboard displays:
- **Size**: Should be ~165 MB (not 147 MB)
- **Latest scrape**: Should show TODAY's date
- **Total products**: Should increase over time
- **Stores**: Should show 6 stores (if all scraped)

## Best Practices

### Daily Update Routine

```bash
# After scraping completes
python scripts/update_streamlit.py

# Copy URL from output
# Paste into Streamlit Cloud secrets
# Wait ~8 minutes
# Verify dashboard updated
```

### Weekly Verification

Check dashboard shows:
- ✅ Latest data (< 24h old)
- ✅ Correct database size (165+ MB)
- ✅ All stores present
- ✅ No error messages

### Monthly Maintenance

1. **Check SAS URL expiry**:
   - URLs expire after 1 year
   - Regenerate before expiry:
     ```bash
     python -m scripts.cli sync --layer analytics
     ```

2. **Clean old backups** (Azure Portal):
   - Container: `analytics`
   - Folder: `backups/`
   - Keep last 30 days, delete older

3. **Verify incremental sync**:
   ```bash
   python -m scripts.cli sync --layer status
   ```
   - Should show most files already synced
   - Only new scrapes pending

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Local Environment                                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Scraping → Bronze Parquet → DBT Transform → analytics.duckdb│
│                                      ↓                        │
│                         python scripts/update_streamlit.py   │
│                                      ↓                        │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│ Azure Blob Storage                                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Container: analytics/                                       │
│    ├── analytics.duckdb (latest, 165 MB)                    │
│    └── backups/analytics_YYYYMMDD_HHMMSS.duckdb            │
│                                      ↓                        │
│                         Generate SAS URL (1 year validity)   │
│                                      ↓                        │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│ Streamlit Cloud                                              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Read secret: db_download_url                            │
│  2. Compare with cached URL (data/.db_url_cache)            │
│  3. If changed:                                              │
│     - Delete old database                                    │
│     - Download new (165 MB, ~2 min)                         │
│     - Cache new URL                                          │
│  4. Connect to DuckDB                                        │
│  5. Display dashboard with latest data                       │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Code Reference

| File | Purpose |
|------|---------|
| [src/dashboard/utils/db_manager.py](../../src/dashboard/utils/db_manager.py) | Smart cache invalidation |
| [scripts/update_streamlit.py](../../scripts/update_streamlit.py) | Automated update pipeline |
| [src/storage/azure_blob.py](../../src/storage/azure_blob.py) | Azure upload + SAS generation |
| [scripts/cli.py](../../scripts/cli.py) | CLI sync commands |

## Future Enhancements

- [ ] Webhook-based auto-update (Azure → Streamlit)
- [ ] Version tracking in database metadata
- [ ] Email notifications on update completion
- [ ] Automatic daily sync via GitHub Actions
- [ ] Rollback mechanism (restore previous version)
- [ ] Multi-region CDN for faster downloads

---

**Last Updated**: 2026-02-07
**Implementation**: Smart cache invalidation v1.0
