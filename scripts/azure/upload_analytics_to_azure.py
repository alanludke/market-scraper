"""
Upload analytics.duckdb to Azure Blob Storage for Streamlit Cloud.

Usage:
    python scripts/upload_analytics_to_azure.py

Environment variables required:
    AZURE_ACCOUNT_NAME
    AZURE_ACCOUNT_KEY

Output:
    Public URL for Streamlit Cloud to download the database
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, ContentSettings, generate_blob_sas, BlobSasPermissions
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


def upload_analytics_db():
    """Upload analytics.duckdb to Azure Blob and generate SAS URL."""

    # Configuration
    account_name = os.getenv("AZURE_ACCOUNT_NAME")
    account_key = os.getenv("AZURE_ACCOUNT_KEY")
    container_name = "analytics"  # Separate container for analytics DB

    if not account_name or not account_key:
        print("❌ Error: AZURE_ACCOUNT_NAME and AZURE_ACCOUNT_KEY must be set")
        print("   Set them in .env or environment variables")
        return

    db_path = Path("data/analytics.duckdb")

    if not db_path.exists():
        print(f"❌ Error: {db_path} not found!")
        print("   Run 'cd src/transform/dbt_project && dbt run' first")
        return

    # Connect to Azure
    conn_str = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={account_name};"
        f"AccountKey={account_key};"
        f"EndpointSuffix=core.windows.net"
    )

    blob_service = BlobServiceClient.from_connection_string(conn_str)

    # Create container if not exists (PRIVATE - no public access)
    try:
        container_client = blob_service.get_container_client(container_name)
        if not container_client.exists():
            print(f"📦 Creating private container '{container_name}'...")
            container_client = blob_service.create_container(container_name)
            print(f"✅ Container created successfully")
        else:
            print(f"✅ Container '{container_name}' already exists")
    except Exception as e:
        print(f"⚠️  Container error: {e}")
        return

    # Upload with versioning (keep latest + backup)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    blobs = [
        ("analytics.duckdb", "Latest version (Streamlit uses this)"),
        (f"analytics_backup_{timestamp}.duckdb", "Timestamped backup")
    ]

    size_mb = db_path.stat().st_size / 1024 / 1024
    print(f"\n📊 Uploading {db_path.name} ({size_mb:.1f} MB)...")

    for blob_name, description in blobs:
        print(f"\n📤 {description}...")
        print(f"   → {blob_name}")

        blob_client = blob_service.get_blob_client(
            container=container_name,
            blob=blob_name
        )

        with open(db_path, "rb") as data:
            blob_client.upload_blob(
                data,
                overwrite=True,
                content_settings=ContentSettings(content_type="application/x-duckdb")
            )

        if blob_name == "analytics.duckdb":
            # Generate SAS token (valid for 1 year)
            sas_token = generate_blob_sas(
                account_name=account_name,
                account_key=account_key,
                container_name=container_name,
                blob_name=blob_name,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(days=365)
            )

            sas_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"

            print(f"\n✅ Upload successful!")
            print(f"\n📋 Next steps:")
            print(f"\n1. Copy this SAS URL (valid for 1 year):")
            print(f"\n{sas_url}")
            print(f"\n2. Go to Streamlit Cloud → Settings → Secrets")
            print(f"\n3. Add this secret:")
            print(f'\ndb_download_url = "{sas_url}"')
            print(f"\n4. Reboot your Streamlit app or clear cache")
            print(f"\n🔄 The app will download the updated database on next access.")
            print(f"\n💡 Tip: Re-run this script whenever you want to update the database!")

            # Also save to file for reference
            url_file = Path("azure_analytics_url.txt")
            url_file.write_text(sas_url)
            print(f"\n📝 SAS URL also saved to: {url_file}")


if __name__ == "__main__":
    try:
        from azure.storage.blob import BlobServiceClient, ContentSettings
    except ImportError:
        print("❌ Error: azure-storage-blob not installed")
        print("   Run: pip install azure-storage-blob")
        exit(1)

    upload_analytics_db()