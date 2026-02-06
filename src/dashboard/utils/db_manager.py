"""
Database Manager for Streamlit Dashboard
Handles automatic database download and caching
"""

import streamlit as st
import duckdb
from pathlib import Path
import os


@st.cache_resource
def get_duckdb_connection():
    """
    Get DuckDB connection with automatic database download.

    Priority order:
    1. Local file (data/analytics.duckdb)
    2. Download from URL (if DB_DOWNLOAD_URL secret is set)
    3. Sample/demo database (if available)

    Returns:
        duckdb.Connection: Read-only connection to analytics database
    """
    db_path = Path("data/analytics.duckdb")

    # Check if database exists locally
    if db_path.exists():
        st.success(f"✅ Database loaded: {db_path} ({db_path.stat().st_size / 1024 / 1024:.1f} MB)")
        return duckdb.connect(str(db_path), read_only=True)

    # Try to download from configured URL
    if "db_download_url" in st.secrets:
        return _download_and_connect(db_path, st.secrets["db_download_url"])

    # Check for alternative paths (for local development)
    alternative_paths = [
        Path(__file__).parent.parent.parent.parent / "data" / "analytics.duckdb",
        Path("../data/analytics.duckdb"),
        Path("../../data/analytics.duckdb"),
    ]

    for alt_path in alternative_paths:
        if alt_path.exists():
            st.info(f"📁 Using database from: {alt_path}")
            return duckdb.connect(str(alt_path), read_only=True)

    # No database available
    st.error("""
    ❌ **Database not found!**

    Please configure one of the following:

    1. **Upload database**: Place `analytics.duckdb` in `data/` folder
    2. **Configure download URL**: Add `db_download_url` to Streamlit secrets
    3. **Use sample data**: Run DBT locally to generate analytics.duckdb

    See [STREAMLIT_DEPLOY.md](https://github.com/alanludke/market-scraper/blob/master/STREAMLIT_DEPLOY.md) for instructions.
    """)
    st.stop()


def _download_and_connect(db_path: Path, download_url: str) -> duckdb.Connection:
    """Download database from URL and connect."""
    import requests

    db_path.parent.mkdir(parents=True, exist_ok=True)

    with st.spinner("📥 Downloading database (first time only)..."):
        try:
            response = requests.get(download_url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))

            # Download with progress bar
            progress_bar = st.progress(0)
            downloaded = 0

            with open(db_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress_bar.progress(downloaded / total_size)

            st.success(f"✅ Database downloaded: {db_path.stat().st_size / 1024 / 1024:.1f} MB")
            return duckdb.connect(str(db_path), read_only=True)

        except Exception as e:
            st.error(f"❌ Failed to download database: {e}")
            if db_path.exists():
                db_path.unlink()  # Remove partial download
            st.stop()


def get_database_info(conn: duckdb.Connection) -> dict:
    """Get metadata about the database."""
    try:
        info = {}

        # Database size
        db_path = Path("data/analytics.duckdb")
        if db_path.exists():
            info['size_mb'] = db_path.stat().st_size / 1024 / 1024

        # Latest scrape date
        result = conn.execute("""
            SELECT MAX(scraped_at) FROM dev_local.tru_product
        """).fetchone()
        info['latest_scrape'] = result[0] if result else None

        # Record counts
        info['total_products'] = conn.execute("""
            SELECT COUNT(DISTINCT product_id) FROM dev_local.tru_product
        """).fetchone()[0]

        info['total_stores'] = conn.execute("""
            SELECT COUNT(DISTINCT supermarket) FROM dev_local.tru_product
        """).fetchone()[0]

        return info

    except Exception as e:
        st.warning(f"Could not load database info: {e}")
        return {}
