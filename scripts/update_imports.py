"""
Update imports after project reorganization.

This script automatically updates import statements to reflect the new project structure.

Usage:
    python scripts/update_imports.py --dry-run  # Preview changes
    python scripts/update_imports.py            # Execute updates
"""

import re
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
from loguru import logger

# Configure logger
logger.add(
    "data/logs/update_imports_{time}.log",
    rotation="10 MB",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)


class ImportUpdater:
    """Updates import statements after reorganization."""

    # Map old imports to new imports
    IMPORT_MAPPINGS = {
        # CLI modules
        r"from scripts\.cli import": "from src.cli.scraper import",
        r"import scripts\.cli": "import src.cli.scraper",
        r"from scripts\.cli_enrich import": "from src.cli.enrichment import",
        r"import scripts\.cli_enrich": "import src.cli.enrichment",
        r"from scripts\.cli_validate_deals import": "from src.cli.validation import",
        r"import scripts\.cli_validate_deals": "import src.cli.validation",

        # Orchestration modules
        r"from src.orchestration.runner import": "from src.orchestration.runner import",
        r"import src.orchestration.runner": "import src.orchestration.runner",
        r"from src.orchestration.standalone_runner import": "from src.orchestration.standalone_runner import",
        r"import src.orchestration.standalone_runner": "import src.orchestration.standalone_runner",

        # Script modules (maintenance)
        r"from scripts\.check_old_scraper import": "from scripts.maintenance.check_old_scraper import",
        r"import scripts\.check_old_scraper": "import scripts.maintenance.check_old_scraper",
        r"from scripts\.check_running_scraper import": "from scripts.maintenance.check_running_scraper import",
        r"import scripts\.check_running_scraper": "import scripts.maintenance.check_running_scraper",
        r"from scripts\.validate_hot_deals_quality import": "from scripts.maintenance.validate_hot_deals_quality import",
        r"import scripts\.validate_hot_deals_quality": "import scripts.maintenance.validate_hot_deals_quality",

        # Script modules (monitoring)
        r"from scripts\.monitor_scrape import": "from scripts.monitoring.monitor_scrape import",
        r"import scripts\.monitor_scrape": "import scripts.monitoring.monitor_scrape",

        # Script modules (azure)
        r"from scripts\.upload_analytics_to_azure import": "from scripts.azure.upload_analytics_to_azure import",
        r"import scripts\.upload_analytics_to_azure": "import scripts.azure.upload_analytics_to_azure",
        r"from scripts\.update_streamlit import": "from scripts.azure.update_streamlit import",
        r"import scripts\.update_streamlit": "import scripts.azure.update_streamlit",

        # Dashboard (remove app.py references, use src.dashboard.app)
        r"import src.dashboard.app": "import src.dashboard.app",
        r"from src.dashboard.app import": "from src.dashboard.app import",
    }

    def __init__(self, root: Path, dry_run: bool = False):
        self.root = root
        self.dry_run = dry_run
        self.stats = {
            "files_scanned": 0,
            "files_updated": 0,
            "imports_updated": 0
        }

    def update_file(self, file_path: Path) -> bool:
        """Update imports in a single file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content
            updates_made = 0

            # Apply all import mappings
            for old_pattern, new_import in self.IMPORT_MAPPINGS.items():
                matches = re.findall(old_pattern, content)
                if matches:
                    content = re.sub(old_pattern, new_import, content)
                    updates_made += len(matches)

            self.stats["files_scanned"] += 1

            if content != original_content:
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would update: {file_path}")
                    logger.info(f"  {updates_made} import(s) changed")
                else:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    logger.info(f"✓ Updated: {file_path}")
                    logger.info(f"  {updates_made} import(s) changed")

                self.stats["files_updated"] += 1
                self.stats["imports_updated"] += updates_made
                return True

            return False

        except Exception as e:
            logger.error(f"Error updating {file_path}: {e}")
            return False

    def scan_and_update(self) -> None:
        """Scan all Python files and update imports."""
        logger.info("Scanning for files to update...")

        # Find all Python files (excluding virtualenv and cache)
        python_files = []
        for pattern in ["src/**/*.py", "scripts/**/*.py", "tests/**/*.py", "src/dashboard/pages/**/*.py"]:
            python_files.extend(self.root.glob(pattern))

        # Filter out __pycache__ and .venv
        python_files = [
            f for f in python_files
            if "__pycache__" not in str(f) and ".venv" not in str(f)
        ]

        logger.info(f"Found {len(python_files)} Python files")

        # Update each file
        for file_path in python_files:
            self.update_file(file_path)

    def print_summary(self) -> None:
        """Print update summary."""
        logger.info("\n" + "=" * 60)
        logger.info("IMPORT UPDATE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Files scanned: {self.stats['files_scanned']}")
        logger.info(f"Files updated: {self.stats['files_updated']}")
        logger.info(f"Imports updated: {self.stats['imports_updated']}")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Update imports after reorganization")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run - preview changes without executing"
    )

    args = parser.parse_args()

    # Initialize updater
    root = Path.cwd()
    updater = ImportUpdater(root=root, dry_run=args.dry_run)

    # Scan and update
    updater.scan_and_update()

    # Print summary
    updater.print_summary()

    if args.dry_run:
        logger.info("\nℹ️  This was a DRY RUN - no files were modified")
        logger.info("Run without --dry-run to apply the changes")


if __name__ == "__main__":
    main()
