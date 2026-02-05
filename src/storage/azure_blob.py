"""
Azure Blob Storage upload for bronze layer data.

Usage:
    from src.storage.azure_blob import BlobUploader

    uploader = BlobUploader()  # reads from env vars
    uploader.upload_run("data/bronze/supermarket=bistek/region=floripa/.../run_20260205_120000")

Requires:
    pip install azure-storage-blob
    Environment variables: AZURE_ACCOUNT_NAME, AZURE_ACCOUNT_KEY
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger("market_scraper")

CONTAINER_NAME = "bronze"


class BlobUploader:
    def __init__(
        self,
        account_name: str | None = None,
        account_key: str | None = None,
        container: str = CONTAINER_NAME,
    ):
        self.account_name = account_name or os.getenv("AZURE_ACCOUNT_NAME", "")
        self.account_key = account_key or os.getenv("AZURE_ACCOUNT_KEY", "")
        self.container = container
        self._client = None

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

    def upload_file(self, local_path: Path, blob_path: str):
        client = self._get_client()
        blob_client = client.get_blob_client(
            container=self.container, blob=blob_path
        )
        with open(local_path, "rb") as f:
            blob_client.upload_blob(f, overwrite=True)
        logger.info(f"Uploaded {local_path.name} -> {blob_path}")

    def upload_run(self, run_dir: str | Path):
        """Upload all JSONL files from a run directory preserving the bronze path structure."""
        run_dir = Path(run_dir)
        if not run_dir.exists():
            logger.error(f"Run directory not found: {run_dir}")
            return

        for jsonl_file in run_dir.glob("*.jsonl"):
            # Preserve the path structure from data/bronze/ onwards
            relative = jsonl_file.relative_to(Path("data"))
            blob_path = str(relative).replace("\\", "/")
            self.upload_file(jsonl_file, blob_path)

    def upload_latest(self, store_name: str):
        """Find and upload the most recent run for a given store."""
        bronze_dir = Path(f"data/bronze/supermarket={store_name}")
        if not bronze_dir.exists():
            logger.error(f"No data found for {store_name}")
            return

        # Find latest run directories
        run_dirs = sorted(bronze_dir.rglob("run_*"), key=lambda p: p.name, reverse=True)
        if not run_dirs:
            logger.error(f"No runs found for {store_name}")
            return

        latest_run_id = run_dirs[0].name
        for run_dir in run_dirs:
            if run_dir.name == latest_run_id:
                self.upload_run(run_dir)
