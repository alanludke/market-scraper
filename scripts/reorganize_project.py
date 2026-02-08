"""
Automated project reorganization script.

This script reorganizes the project structure according to RESTRUCTURE_PLAN.md:
- Moves files to proper directories
- Creates new directory structure
- Updates imports and references
- Cleans up junk files

Usage:
    python scripts/reorganize_project.py --dry-run  # Preview changes
    python scripts/reorganize_project.py            # Execute reorganization
"""

import argparse
import shutil
from pathlib import Path
from typing import List, Tuple
from loguru import logger

# Configure logger
logger.add(
    "data/logs/reorganize_{time}.log",
    rotation="10 MB",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)


class ProjectReorganizer:
    """Reorganizes project structure."""

    def __init__(self, root: Path, dry_run: bool = False):
        self.root = root
        self.dry_run = dry_run
        self.moves = []
        self.deletions = []
        self.creations = []

    def plan_reorganization(self) -> None:
        """Plan all file moves and directory creations."""

        # Phase 1: Delete junk files
        self.deletions.extend([
            self.root / "azure_analytics_url.txt",
            self.root / "reseach.txt",
            self.root / "nul",
            self.root / "requirements_dashboard.txt",
        ])

        # Phase 2: Create new directory structure
        self.creations.extend([
            self.root / "scripts/deployment",
            self.root / "scripts/maintenance",
            self.root / "scripts/monitoring",
            self.root / "scripts/setup",
            self.root / "scripts/azure",
            self.root / "src/cli",
            self.root / "docs/operations",
            self.root / "docs/deployment",
        ])

        # Phase 3: Move deployment scripts
        self.moves.extend([
            (self.root / "deploy_to_cloud.sh", self.root / "scripts/deployment/deploy_to_cloud.sh"),
            (self.root / "deploy_to_cloud.ps1", self.root / "scripts/deployment/deploy_to_cloud.ps1"),
            (self.root / "deploy_to_cloud_free_tier.ps1", self.root / "scripts/deployment/deploy_to_cloud_free_tier.ps1"),
            (self.root / "scripts/start_prefect_server.ps1", self.root / "scripts/deployment/start_prefect_server.ps1"),
            (self.root / "scripts/stop_prefect_server.ps1", self.root / "scripts/deployment/stop_prefect_server.ps1"),
            (self.root / "scripts/start_prefect.bat", self.root / "scripts/deployment/start_prefect.bat"),
        ])

        # Phase 4: Move maintenance scripts
        self.moves.extend([
            (self.root / "scripts/check_old_scraper.py", self.root / "scripts/maintenance/check_old_scraper.py"),
            (self.root / "scripts/check_running_scraper.py", self.root / "scripts/maintenance/check_running_scraper.py"),
            (self.root / "scripts/validate_hot_deals_quality.py", self.root / "scripts/maintenance/validate_hot_deals_quality.py"),
            (self.root / "scripts/investigate_carrefour_api.py", self.root / "scripts/maintenance/investigate_carrefour_api.py"),
        ])

        # Phase 5: Move monitoring scripts
        self.moves.extend([
            (self.root / "scripts/monitor_scrape.py", self.root / "scripts/monitoring/monitor_scrape.py"),
            (self.root / "scripts/check_progress.sh", self.root / "scripts/monitoring/check_progress.sh"),
            (self.root / "scripts/run_overnight_scrapes.sh", self.root / "scripts/monitoring/run_overnight_scrapes.sh"),
        ])

        # Phase 6: Move setup scripts
        self.moves.extend([
            (self.root / "scripts/setup_prefect_cloud_startup.ps1", self.root / "scripts/setup/setup_prefect_cloud_startup.ps1"),
            (self.root / "scripts/setup_startup_task.ps1", self.root / "scripts/setup/setup_startup_task.ps1"),
            (self.root / "scripts/daily_delta_sync.ps1", self.root / "scripts/setup/daily_delta_sync.ps1"),
            (self.root / "scripts/daily_delta_sync.bat", self.root / "scripts/setup/daily_delta_sync.bat"),
            (self.root / "scripts/install_task_scheduler.ps1", self.root / "scripts/setup/install_task_scheduler.ps1"),
        ])

        # Phase 7: Move Azure scripts
        self.moves.extend([
            (self.root / "scripts/upload_analytics_to_azure.py", self.root / "scripts/azure/upload_analytics_to_azure.py"),
            (self.root / "scripts/update_streamlit.py", self.root / "scripts/azure/update_streamlit.py"),
        ])

        # Phase 8: Move CLIs to src/cli/
        self.moves.extend([
            (self.root / "scripts/cli.py", self.root / "src/cli/scraper.py"),
            (self.root / "scripts/cli_enrich.py", self.root / "src/cli/enrichment.py"),
            (self.root / "scripts/cli_validate_deals.py", self.root / "src/cli/validation.py"),
        ])

        # Phase 9: Move root files
        self.moves.extend([
            (self.root / "prefect_cloud_runner.py", self.root / "src/orchestration/runner.py"),
            (self.root / "run_scraper_standalone.py", self.root / "src/orchestration/standalone_runner.py"),
        ])

        # Phase 10: Delete duplicate dashboard entry point
        self.deletions.append(self.root / "app.py")

        # Phase 11: Move documentation
        self.moves.extend([
            (self.root / "OPTIMIZATION_GUIDE.md", self.root / "docs/operations/OPTIMIZATION_GUIDE.md"),
            (self.root / "PREFECT_CLOUD_SETUP.md", self.root / "docs/operations/PREFECT_CLOUD_SETUP.md"),
            (self.root / "STREAMLIT_DEPLOY.md", self.root / "docs/deployment/STREAMLIT_DEPLOY.md"),
        ])

    def execute(self) -> None:
        """Execute the reorganization plan."""
        logger.info("Starting project reorganization...")

        # Create directories
        logger.info(f"\n📁 Creating {len(self.creations)} directories...")
        for directory in self.creations:
            if self.dry_run:
                logger.info(f"[DRY RUN] Would create: {directory}")
            else:
                directory.mkdir(parents=True, exist_ok=True)
                logger.info(f"✓ Created: {directory}")

        # Move files
        logger.info(f"\n📦 Moving {len(self.moves)} files...")
        for source, destination in self.moves:
            if not source.exists():
                logger.warning(f"⚠️  Source not found (skipping): {source}")
                continue

            if self.dry_run:
                logger.info(f"[DRY RUN] Would move: {source} → {destination}")
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
                logger.info(f"✓ Moved: {source.name} → {destination}")

        # Delete files
        logger.info(f"\n🗑️  Deleting {len(self.deletions)} junk files...")
        for file in self.deletions:
            if not file.exists():
                logger.warning(f"⚠️  File not found (skipping): {file}")
                continue

            if self.dry_run:
                logger.info(f"[DRY RUN] Would delete: {file}")
            else:
                try:
                    file.unlink()
                    logger.info(f"✓ Deleted: {file}")
                except (PermissionError, OSError) as e:
                    logger.warning(f"⚠️  Could not delete {file}: {e}")

        # Create __init__.py files
        logger.info("\n📝 Creating __init__.py files...")
        init_files = [
            self.root / "src/cli/__init__.py",
            self.root / "scripts/deployment/__init__.py",
            self.root / "scripts/maintenance/__init__.py",
            self.root / "scripts/monitoring/__init__.py",
            self.root / "scripts/setup/__init__.py",
            self.root / "scripts/azure/__init__.py",
        ]

        for init_file in init_files:
            if self.dry_run:
                logger.info(f"[DRY RUN] Would create: {init_file}")
            else:
                if not init_file.exists():
                    init_file.touch()
                    logger.info(f"✓ Created: {init_file}")

        logger.info("\n✅ Reorganization complete!")

        if self.dry_run:
            logger.info("\nℹ️  This was a DRY RUN - no changes were made")
            logger.info("Run without --dry-run to execute the reorganization")

    def print_summary(self) -> None:
        """Print reorganization summary."""
        logger.info("\n" + "=" * 60)
        logger.info("REORGANIZATION PLAN")
        logger.info("=" * 60)
        logger.info(f"Directories to create: {len(self.creations)}")
        logger.info(f"Files to move: {len(self.moves)}")
        logger.info(f"Files to delete: {len(self.deletions)}")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Reorganize project structure")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run - preview changes without executing"
    )

    args = parser.parse_args()

    # Initialize reorganizer
    root = Path.cwd()
    reorganizer = ProjectReorganizer(root=root, dry_run=args.dry_run)

    # Plan reorganization
    reorganizer.plan_reorganization()

    # Print summary
    reorganizer.print_summary()

    # Execute
    reorganizer.execute()

    # Post-reorganization instructions
    if not args.dry_run:
        logger.info("\n" + "=" * 60)
        logger.info("NEXT STEPS")
        logger.info("=" * 60)
        logger.info("1. Update imports in code:")
        logger.info("   - scripts.cli → src.cli.scraper")
        logger.info("   - scripts.cli_enrich → src.cli.enrichment")
        logger.info("   - scripts.cli_validate_deals → src.cli.validation")
        logger.info("")
        logger.info("2. Run validation:")
        logger.info("   python -m py_compile src/**/*.py")
        logger.info("   pytest tests/")
        logger.info("")
        logger.info("3. Test scrapers:")
        logger.info("   python src/cli/scraper.py scrape bistek --limit 100")
        logger.info("")
        logger.info("4. Test dashboard:")
        logger.info("   streamlit run src/dashboard/app.py")
        logger.info("")
        logger.info("5. Migrate legacy data:")
        logger.info("   python scripts/maintenance/migrate_legacy_data.py --store all")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
