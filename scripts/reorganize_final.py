"""
Final project reorganization - colocation principle.

Move remaining root directories to their logical locations:
- config/ → src/ingest/config/ (scraper configurations)
- logs/ → src/observability/logs/ (application logs)
- pages/ → src/dashboard/pages/ (Streamlit pages)
- tests/ → tests/ (keep at root, Python convention)

Usage:
    python scripts/reorganize_final.py --dry-run  # Preview changes
    python scripts/reorganize_final.py            # Execute
"""

import argparse
import shutil
from pathlib import Path
from loguru import logger

# Configure logger
logger.add(
    "data/logs/reorganize_final_{time}.log",
    rotation="10 MB",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)


class FinalReorganizer:
    """Final reorganization following colocation principle."""

    def __init__(self, root: Path, dry_run: bool = False):
        self.root = root
        self.dry_run = dry_run
        self.moves = []

    def plan_reorganization(self) -> None:
        """Plan final moves based on colocation principle."""

        # 1. config/ → src/ingest/config/ (scraper configurations)
        config_src = self.root / "config"
        config_dst = self.root / "src/ingest/config"
        if config_src.exists():
            self.moves.append((config_src, config_dst, "Scraper configurations"))

        # 2. logs/ → src/observability/logs/ (application logs)
        logs_src = self.root / "logs"
        logs_dst = self.root / "src/observability/logs"
        if logs_src.exists():
            self.moves.append((logs_src, logs_dst, "Application logs"))

        # 3. pages/ → src/dashboard/pages/ (Streamlit pages)
        pages_src = self.root / "pages"
        pages_dst = self.root / "src/dashboard/pages"
        if pages_src.exists():
            self.moves.append((pages_src, pages_dst, "Streamlit pages"))

    def execute(self) -> None:
        """Execute the reorganization."""
        logger.info("Starting final reorganization (colocation principle)...")

        if not self.moves:
            logger.warning("No directories to move (already organized or missing)")
            return

        logger.info(f"\n📦 Moving {len(self.moves)} directories...\n")

        for source, destination, description in self.moves:
            if not source.exists():
                logger.warning(f"⚠️  Source not found (skipping): {source}")
                continue

            if self.dry_run:
                logger.info(f"[DRY RUN] Would move: {source} → {destination}")
                logger.info(f"  Description: {description}")
            else:
                # Create destination parent
                destination.parent.mkdir(parents=True, exist_ok=True)

                # Move directory
                shutil.move(str(source), str(destination))
                logger.info(f"✓ Moved: {source.name} → {destination}")
                logger.info(f"  {description}")

        logger.info("\n✅ Final reorganization complete!")

        if self.dry_run:
            logger.info("\nℹ️  This was a DRY RUN - no changes were made")
            logger.info("Run without --dry-run to execute the reorganization")

    def print_summary(self) -> None:
        """Print reorganization summary."""
        logger.info("\n" + "=" * 60)
        logger.info("FINAL REORGANIZATION PLAN (Colocation)")
        logger.info("=" * 60)
        for source, destination, description in self.moves:
            logger.info(f"• {source.name}/ → {destination}")
            logger.info(f"  {description}")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Final reorganization following colocation principle"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without executing"
    )

    args = parser.parse_args()

    # Initialize reorganizer
    root = Path.cwd()
    reorganizer = FinalReorganizer(root=root, dry_run=args.dry_run)

    # Plan reorganization
    reorganizer.plan_reorganization()

    # Print summary
    reorganizer.print_summary()

    # Execute
    reorganizer.execute()

    if not args.dry_run:
        logger.info("\n" + "=" * 60)
        logger.info("NEXT STEPS")
        logger.info("=" * 60)
        logger.info("1. Update Streamlit config (.streamlit/config.toml)")
        logger.info("   pages_dir should reference src/dashboard/pages/")
        logger.info("")
        logger.info("2. Update logging config (src/observability/logging_config.py)")
        logger.info("   Log paths should reference src/observability/logs/")
        logger.info("")
        logger.info("3. Update scraper imports")
        logger.info("   from src.ingest.config.stores import → from src.ingest.config.stores import")
        logger.info("")
        logger.info("4. Test everything:")
        logger.info("   python src/cli/scraper.py scrape bistek --limit 100")
        logger.info("   streamlit run src/dashboard/app.py")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
