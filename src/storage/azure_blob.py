"""
Azure Blob Storage - Data Lakehouse Sync.

Uploads local data layers (bronze, analytics) to Azure Blob Storage
preserving Hive-style partitioning for lakehouse compatibility.

Container structure:
    stomarketscraper/
    ├── bronze/          # Raw Parquet from scrapers (immutable)
    ├── analytics/       # DuckDB databases for Streamlit
    └── metadata/        # Sync manifests, logs

Usage:
    from src.storage.azure_blob import LakehouseSync

    sync = LakehouseSync()  # reads from .env
    sync.sync_bronze()      # incremental upload of bronze Parquet
    sync.sync_analytics()   # upload analytics.duckdb + generate SAS URL

CLI:
    python scripts/cli.py sync --layer bronze
    python scripts/cli.py sync --layer analytics
    python scripts/cli.py sync --layer all

Requires:
    pip install azure-storage-blob python-dotenv
    Environment variables: AZURE_ACCOUNT_NAME, AZURE_ACCOUNT_KEY
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# Lakehouse containers
CONTAINERS = {
    "bronze": "bronze",
    "analytics": "analytics",
    "metadata": "metadata",
}

MANIFEST_PATH = Path("data/metadata/sync_manifest.json")


class LakehouseSync:
    """Incremental sync of local data to Azure Blob Storage lakehouse."""

    def __init__(
        self,
        account_name: str | None = None,
        account_key: str | None = None,
    ):
        self.account_name = account_name or os.getenv("AZURE_ACCOUNT_NAME", "")
        self.account_key = account_key or os.getenv("AZURE_ACCOUNT_KEY", "")
        self._client = None
        self._manifest = self._load_manifest()

    def _get_client(self):
        if self._client is None:
            try:
                from azure.storage.blob import BlobServiceClient
            except ImportError:
                raise ImportError(
                    "azure-storage-blob not installed. "
                    "Run: pip install azure-storage-blob"
                )
            conn_str = (
                f"DefaultEndpointsProtocol=https;"
                f"AccountName={self.account_name};"
                f"AccountKey={self.account_key};"
                f"EndpointSuffix=core.windows.net"
            )
            self._client = BlobServiceClient.from_connection_string(conn_str)
        return self._client

    # ── Manifest (incremental tracking) ──────────────────────

    def _load_manifest(self) -> dict:
        if MANIFEST_PATH.exists():
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return {"synced_files": {}, "last_sync": None}

    def _save_manifest(self):
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._manifest["last_sync"] = datetime.now().isoformat()
        MANIFEST_PATH.write_text(
            json.dumps(self._manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _is_synced(self, local_path: Path) -> bool:
        """Check if file was already synced (same path + same size)."""
        key = str(local_path)
        if key not in self._manifest["synced_files"]:
            return False
        return self._manifest["synced_files"][key]["size"] == local_path.stat().st_size

    def _mark_synced(self, local_path: Path, blob_path: str):
        self._manifest["synced_files"][str(local_path)] = {
            "blob_path": blob_path,
            "size": local_path.stat().st_size,
            "synced_at": datetime.now().isoformat(),
        }

    # ── Container management ─────────────────────────────────

    def _ensure_container(self, container_name: str):
        client = self._get_client()
        container_client = client.get_container_client(container_name)
        if not container_client.exists():
            logger.info(f"Creating container '{container_name}'")
            client.create_container(container_name)

    def ensure_all_containers(self):
        for name in CONTAINERS.values():
            self._ensure_container(name)
        logger.info(f"All containers verified: {list(CONTAINERS.values())}")

    # ── Upload helpers ───────────────────────────────────────

    def _upload_file(self, local_path: Path, container: str, blob_path: str):
        client = self._get_client()
        blob_client = client.get_blob_client(container=container, blob=blob_path)
        with open(local_path, "rb") as f:
            blob_client.upload_blob(f, overwrite=True)

    # ── Bronze sync ──────────────────────────────────────────

    def sync_bronze(self, force: bool = False) -> dict:
        """
        Incremental sync of bronze Parquet files to Azure.

        Preserves the local Hive partitioning structure:
            data/bronze/supermarket=X/region=Y/year=Z/month=M/day=D/run_*/...
            → bronze container: supermarket=X/region=Y/year=Z/month=M/day=D/run_*/...

        Args:
            force: If True, re-upload all files (ignore manifest).

        Returns:
            dict with sync stats (uploaded, skipped, errors, total_bytes).
        """
        bronze_dir = Path("data/bronze")
        if not bronze_dir.exists():
            logger.error("No bronze directory found at data/bronze/")
            return {"uploaded": 0, "skipped": 0, "errors": 0}

        self._ensure_container(CONTAINERS["bronze"])

        parquet_files = list(bronze_dir.rglob("*.parquet"))
        total = len(parquet_files)
        stats = {"uploaded": 0, "skipped": 0, "errors": 0, "total_bytes": 0}

        logger.info(f"Bronze sync: {total} Parquet files found")

        for i, local_path in enumerate(parquet_files, 1):
            # Skip already synced files (unless force)
            if not force and self._is_synced(local_path):
                stats["skipped"] += 1
                continue

            # Preserve path relative to data/bronze/ as blob path
            blob_path = str(local_path.relative_to(bronze_dir)).replace("\\", "/")

            try:
                self._upload_file(local_path, CONTAINERS["bronze"], blob_path)
                self._mark_synced(local_path, blob_path)
                stats["uploaded"] += 1
                stats["total_bytes"] += local_path.stat().st_size

                if stats["uploaded"] % 50 == 0 or i == total:
                    uploaded_mb = stats["total_bytes"] / 1024 / 1024
                    logger.info(
                        f"Progress: {i}/{total} files "
                        f"({stats['uploaded']} uploaded, "
                        f"{stats['skipped']} skipped, "
                        f"{uploaded_mb:.1f} MB)"
                    )
                    # Checkpoint manifest periodically
                    self._save_manifest()

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Failed to upload {local_path.name}: {e}")

        self._save_manifest()

        uploaded_mb = stats["total_bytes"] / 1024 / 1024
        logger.info(
            f"Bronze sync complete: "
            f"{stats['uploaded']} uploaded, "
            f"{stats['skipped']} skipped, "
            f"{stats['errors']} errors, "
            f"{uploaded_mb:.1f} MB transferred"
        )
        return stats

    # ── Analytics sync ───────────────────────────────────────

    def sync_analytics(self) -> str | None:
        """
        Upload analytics.duckdb to Azure and return SAS URL.

        Returns:
            SAS URL string for Streamlit Cloud, or None on failure.
        """
        from azure.storage.blob import BlobSasPermissions, generate_blob_sas

        db_path = Path("data/analytics.duckdb")
        if not db_path.exists():
            logger.error("analytics.duckdb not found. Run 'dbt run' first.")
            return None

        self._ensure_container(CONTAINERS["analytics"])

        size_mb = db_path.stat().st_size / 1024 / 1024
        blob_name = "analytics.duckdb"

        # Upload latest version
        logger.info(f"Uploading analytics.duckdb ({size_mb:.1f} MB)...")
        self._upload_file(db_path, CONTAINERS["analytics"], blob_name)

        # Upload timestamped backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backups/analytics_{timestamp}.duckdb"
        self._upload_file(db_path, CONTAINERS["analytics"], backup_name)
        logger.info(f"Backup created: {backup_name}")

        # Generate SAS URL (valid 1 year)
        sas_token = generate_blob_sas(
            account_name=self.account_name,
            account_key=self.account_key,
            container_name=CONTAINERS["analytics"],
            blob_name=blob_name,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(days=365),
        )

        sas_url = (
            f"https://{self.account_name}.blob.core.windows.net/"
            f"{CONTAINERS['analytics']}/{blob_name}?{sas_token}"
        )

        # Save URL locally
        url_file = Path("azure_analytics_url.txt")
        url_file.write_text(sas_url)

        logger.info(f"Analytics sync complete. SAS URL saved to {url_file}")
        return sas_url

    # ── Full sync ────────────────────────────────────────────

    def sync_all(self, force: bool = False) -> dict:
        """Run full lakehouse sync: bronze + analytics."""
        self.ensure_all_containers()

        results = {}

        logger.info("=== Starting full lakehouse sync ===")

        # Bronze
        logger.info("--- Bronze layer ---")
        results["bronze"] = self.sync_bronze(force=force)

        # Analytics
        logger.info("--- Analytics layer ---")
        sas_url = self.sync_analytics()
        results["analytics"] = {"sas_url": sas_url}

        logger.info("=== Lakehouse sync complete ===")
        return results

    # ── Status ───────────────────────────────────────────────

    def status(self) -> dict:
        """Show sync status: local vs Azure."""
        bronze_dir = Path("data/bronze")
        local_files = list(bronze_dir.rglob("*.parquet")) if bronze_dir.exists() else []
        synced_count = sum(
            1 for f in local_files if self._is_synced(f)
        )

        return {
            "local_files": len(local_files),
            "synced_files": synced_count,
            "pending_files": len(local_files) - synced_count,
            "last_sync": self._manifest.get("last_sync"),
        }
