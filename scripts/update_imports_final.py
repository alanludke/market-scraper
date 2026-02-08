"""
Update imports after final reorganization (colocation).

Updates references to:
- config/ → src/ingest/config/
- logs/ → src/observability/logs/
- pages/ → src/dashboard/pages/

Usage:
    python scripts/update_imports_final.py --dry-run  # Preview
    python scripts/update_imports_final.py            # Execute
"""

import re
import argparse
from pathlib import Path
from loguru import logger

# Configure logger
logger.add(
    "data/logs/update_imports_final_{time}.log",
    rotation="10 MB",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)


class FinalImportUpdater:
    """Updates imports after final reorganization."""

    # Import mappings for colocation changes
    IMPORT_MAPPINGS = {
        # Config imports
        r"from config\.": "from src.ingest.config.",
        r"import config\.": "import src.ingest.config.",
        r'"src/ingest/config/': '"src/ingest/config/',
        r"'src/ingest/config/": "'src/ingest/config/",

        # Log paths (in logging_config.py and other places)
        r'"src/observability/logs/': '"src/observability/logs/',
        r"'src/observability/logs/": "'src/observability/logs/",
        r'Path\("logs"\)': 'Path("src/observability/logs")',
        r"Path\('logs'\)": "Path('src/observability/logs')",

        # Pages paths (in Streamlit config)
        r'"src/dashboard/pages/': '"src/dashboard/pages/',
        r"'src/dashboard/pages/": "'src/dashboard/pages/",
        r'pages_dir = "src/dashboard/pages"': 'pages_dir = "src/dashboard/pages"',
        r"pages_dir = 'src/dashboard/pages'": "pages_dir = 'src/dashboard/pages'",
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

        # Find all Python files
        python_files = []
        for pattern in ["src/**/*.py", "scripts/**/*.py", "tests/**/*.py"]:
            python_files.extend(self.root.glob(pattern))

        # Also check config files
        config_files = list(self.root.glob(".streamlit/**/*.toml"))
        yaml_files = list(self.root.glob("**/*.yaml"))

        all_files = python_files + config_files + yaml_files

        # Filter out __pycache__ and .venv
        all_files = [
            f for f in all_files
            if "__pycache__" not in str(f) and ".venv" not in str(f)
        ]

        logger.info(f"Found {len(all_files)} files to scan")

        # Update each file
        for file_path in all_files:
            self.update_file(file_path)

    def print_summary(self) -> None:
        """Print update summary."""
        logger.info("\n" + "=" * 60)
        logger.info("FINAL IMPORT UPDATE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Files scanned: {self.stats['files_scanned']}")
        logger.info(f"Files updated: {self.stats['files_updated']}")
        logger.info(f"Imports updated: {self.stats['imports_updated']}")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Update imports after final reorganization"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without executing"
    )

    args = parser.parse_args()

    # Initialize updater
    root = Path.cwd()
    updater = FinalImportUpdater(root=root, dry_run=args.dry_run)

    # Scan and update
    updater.scan_and_update()

    # Print summary
    updater.print_summary()

    if args.dry_run:
        logger.info("\nℹ️  This was a DRY RUN - no files were modified")
        logger.info("Run without --dry-run to apply the changes")


if __name__ == "__main__":
    main()
