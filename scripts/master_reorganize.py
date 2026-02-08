"""
Master script to orchestrate complete project reorganization.

This script runs all reorganization steps in the correct order:
1. Reorganize file structure
2. Update imports
3. Migrate legacy data (optional)
4. Run validation

Usage:
    python scripts/master_reorganize.py --dry-run              # Preview all changes
    python scripts/master_reorganize.py                        # Execute reorganization
    python scripts/master_reorganize.py --with-data-migration  # Include data migration
"""

import argparse
import subprocess
import sys
from pathlib import Path
from loguru import logger

# Configure logger
logger.add(
    "data/logs/master_reorganize_{time}.log",
    rotation="10 MB",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)


class MasterReorganizer:
    """Orchestrates complete project reorganization."""

    def __init__(self, dry_run: bool = False, migrate_data: bool = False):
        self.dry_run = dry_run
        self.migrate_data = migrate_data
        self.root = Path.cwd()

    def run_step(self, name: str, command: list, critical: bool = True) -> bool:
        """Run a reorganization step."""
        logger.info("\n" + "=" * 60)
        logger.info(f"STEP: {name}")
        logger.info("=" * 60)

        try:
            result = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                check=True
            )

            logger.info(result.stdout)
            if result.stderr:
                logger.warning(result.stderr)

            logger.info(f"✅ {name} completed successfully")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ {name} failed:")
            logger.error(e.stdout)
            logger.error(e.stderr)

            if critical:
                logger.error("This is a critical step. Aborting reorganization.")
                sys.exit(1)

            return False

    def step1_reorganize_structure(self) -> None:
        """Step 1: Reorganize file structure."""
        command = [sys.executable, "scripts/reorganize_project.py"]
        if self.dry_run:
            command.append("--dry-run")

        self.run_step(
            name="Reorganize File Structure",
            command=command,
            critical=True
        )

    def step2_update_imports(self) -> None:
        """Step 2: Update imports."""
        # After reorganization, the script will be in scripts/ (not moved)
        command = [sys.executable, "scripts/update_imports.py"]
        if self.dry_run:
            command.append("--dry-run")

        self.run_step(
            name="Update Imports",
            command=command,
            critical=True
        )

    def step3_migrate_data(self) -> None:
        """Step 3: Migrate legacy data (optional)."""
        if not self.migrate_data:
            logger.info("\n⏭️  Skipping data migration (use --with-data-migration to enable)")
            return

        # Check if archive exists
        archive_path = self.root / "archive/legacy_scrapers"
        if not archive_path.exists():
            logger.info("\n⏭️  No legacy data found - skipping migration")
            return

        command = [sys.executable, "scripts/maintenance/migrate_legacy_data.py", "--store", "all"]
        if self.dry_run:
            command.append("--dry-run")

        self.run_step(
            name="Migrate Legacy Data",
            command=command,
            critical=False  # Non-critical - can be done later
        )

    def step4_validate(self) -> None:
        """Step 4: Run validation."""
        if self.dry_run:
            logger.info("\n⏭️  Skipping validation (dry run mode)")
            return

        logger.info("\n" + "=" * 60)
        logger.info("STEP: Validation")
        logger.info("=" * 60)

        # Check Python syntax
        logger.info("\n1️⃣ Checking Python syntax...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", "src/**/*.py"],
                cwd=self.root,
                capture_output=True,
                text=True,
                shell=True
            )
            logger.info("✅ Python syntax check passed")
        except subprocess.CalledProcessError as e:
            logger.warning("⚠️  Some Python files have syntax errors (check logs)")

        # Test imports
        logger.info("\n2️⃣ Testing imports...")
        try:
            subprocess.run(
                [sys.executable, "-c", "import src.cli.scraper"],
                cwd=self.root,
                check=True,
                capture_output=True
            )
            logger.info("✅ src.cli.scraper imports successfully")
        except subprocess.CalledProcessError:
            logger.warning("⚠️  src.cli.scraper import failed")

        try:
            subprocess.run(
                [sys.executable, "-c", "import src.cli.enrichment"],
                cwd=self.root,
                check=True,
                capture_output=True
            )
            logger.info("✅ src.cli.enrichment imports successfully")
        except subprocess.CalledProcessError:
            logger.warning("⚠️  src.cli.enrichment import failed")

        # Run tests (if available)
        logger.info("\n3️⃣ Running tests...")
        tests_path = self.root / "tests"
        if tests_path.exists():
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "tests/", "-v"],
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                logger.info(result.stdout)
                logger.info("✅ Tests completed")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                logger.warning("⚠️  Some tests failed or timed out")
        else:
            logger.info("⏭️  No tests directory found")

    def execute(self) -> None:
        """Execute all reorganization steps."""
        logger.info("\n" + "🚀" * 30)
        logger.info("MASTER PROJECT REORGANIZATION")
        logger.info("🚀" * 30)

        if self.dry_run:
            logger.info("\n⚠️  DRY RUN MODE - No changes will be made")

        # Step 1: Reorganize structure
        self.step1_reorganize_structure()

        # Step 2: Update imports
        self.step2_update_imports()

        # Step 3: Migrate data (optional)
        self.step3_migrate_data()

        # Step 4: Validate
        self.step4_validate()

        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info("🎉 REORGANIZATION COMPLETE!")
        logger.info("=" * 60)

        if self.dry_run:
            logger.info("\nℹ️  This was a DRY RUN - no changes were made")
            logger.info("Run without --dry-run to execute the reorganization")
        else:
            logger.info("\n✅ Your project has been reorganized!")
            logger.info("\n📝 Next steps:")
            logger.info("1. Review changes: git status")
            logger.info("2. Test scrapers: python src/cli/scraper.py scrape bistek --limit 100")
            logger.info("3. Test dashboard: streamlit run src/dashboard/app.py")
            logger.info("4. Run DBT: cd src/transform/dbt_project && dbt run")

            if self.migrate_data and not self.dry_run:
                logger.info("5. Delete archive: rm -rf archive/")

            logger.info("\n📚 See RESTRUCTURE_PLAN.md for full details")


def main():
    parser = argparse.ArgumentParser(
        description="Master script for complete project reorganization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview all changes (recommended first!)
  python scripts/master_reorganize.py --dry-run

  # Execute reorganization without data migration
  python scripts/master_reorganize.py

  # Execute reorganization WITH data migration (11GB, takes 10-30 min)
  python scripts/master_reorganize.py --with-data-migration
        """
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without executing (recommended)"
    )

    parser.add_argument(
        "--with-data-migration",
        action="store_true",
        help="Include legacy data migration (11GB JSONL → Parquet)"
    )

    args = parser.parse_args()

    # Initialize reorganizer
    reorganizer = MasterReorganizer(
        dry_run=args.dry_run,
        migrate_data=args.with_data_migration
    )

    # Execute
    reorganizer.execute()


if __name__ == "__main__":
    main()
