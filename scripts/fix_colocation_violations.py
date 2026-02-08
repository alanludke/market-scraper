"""
Fix all colocation violations found in deep-dive audit.

Actions:
1. Move analytics databases to src/analytics/
2. Delete duplicate pages directory (src/dashboard/pages/pages/)
3. Add missing __init__.py
4. Update code references

Usage:
    python scripts/fix_colocation_violations.py --dry-run  # Preview
    python scripts/fix_colocation_violations.py            # Execute
"""

import argparse
import shutil
from pathlib import Path
from loguru import logger

# Configure logger
logger.add(
    "data/logs/fix_colocation_{time}.log",
    rotation="10 MB",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)


class ColocationFixer:
    """Fix colocation violations."""

    def __init__(self, root: Path, dry_run: bool = False):
        self.root = root
        self.dry_run = dry_run
        self.actions = []

    def plan_fixes(self) -> None:
        """Plan all fixes."""

        # 1. Move analytics databases
        market_data_src = self.root / "data/market_data.duckdb"
        market_data_dst = self.root / "src/analytics/market_data.duckdb"
        if market_data_src.exists():
            self.actions.append(("move", market_data_src, market_data_dst, "Analytics database"))

        analytics_db_src = self.root / "data/analytics.duckdb"
        analytics_db_dst = self.root / "src/analytics/analytics.duckdb"
        if analytics_db_src.exists():
            self.actions.append(("move", analytics_db_src, analytics_db_dst, "Analytics database"))

        # 2. Delete duplicate pages directory
        duplicate_pages = self.root / "src/dashboard/pages/pages"
        if duplicate_pages.exists():
            self.actions.append(("delete", duplicate_pages, None, "Duplicate pages directory"))

        # 3. Add missing __init__.py
        utils_init = self.root / "src/dashboard/utils/__init__.py"
        if not utils_init.exists():
            self.actions.append(("create", utils_init, None, "Missing __init__.py"))

    def execute(self) -> None:
        """Execute all fixes."""
        logger.info("Starting colocation fixes...\n")

        if not self.actions:
            logger.info("✅ No fixes needed - project is perfectly organized!")
            return

        logger.info(f"📦 Executing {len(self.actions)} fixes...\n")

        for action_type, source, destination, description in self.actions:
            if action_type == "move":
                self._move(source, destination, description)
            elif action_type == "delete":
                self._delete(source, description)
            elif action_type == "create":
                self._create(source, description)

        logger.info("\n✅ All colocation violations fixed!")

        if self.dry_run:
            logger.info("\nℹ️  This was a DRY RUN - no changes were made")
            logger.info("Run without --dry-run to apply the fixes")

    def _move(self, source: Path, destination: Path, description: str) -> None:
        """Move file."""
        if not source.exists():
            logger.warning(f"⚠️  Source not found (skipping): {source}")
            return

        if self.dry_run:
            logger.info(f"[DRY RUN] Would move: {source.name} → {destination}")
            logger.info(f"  {description}")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            logger.info(f"✓ Moved: {source.name} → {destination}")
            logger.info(f"  {description}")

    def _delete(self, path: Path, description: str) -> None:
        """Delete file or directory."""
        if not path.exists():
            logger.warning(f"⚠️  Path not found (skipping): {path}")
            return

        if self.dry_run:
            logger.info(f"[DRY RUN] Would delete: {path}")
            logger.info(f"  {description}")
        else:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            logger.info(f"✓ Deleted: {path}")
            logger.info(f"  {description}")

    def _create(self, path: Path, description: str) -> None:
        """Create file."""
        if path.exists():
            logger.warning(f"⚠️  File already exists (skipping): {path}")
            return

        if self.dry_run:
            logger.info(f"[DRY RUN] Would create: {path}")
            logger.info(f"  {description}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            logger.info(f"✓ Created: {path}")
            logger.info(f"  {description}")

    def print_summary(self) -> None:
        """Print fix summary."""
        logger.info("\n" + "=" * 60)
        logger.info("COLOCATION FIXES PLAN")
        logger.info("=" * 60)
        for action_type, source, destination, description in self.actions:
            if action_type == "move":
                logger.info(f"• MOVE: {source.name} → {destination}")
            elif action_type == "delete":
                logger.info(f"• DELETE: {source}")
            elif action_type == "create":
                logger.info(f"• CREATE: {source}")
            logger.info(f"  {description}")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Fix colocation violations")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without executing"
    )

    args = parser.parse_args()

    # Initialize fixer
    root = Path.cwd()
    fixer = ColocationFixer(root=root, dry_run=args.dry_run)

    # Plan fixes
    fixer.plan_fixes()

    # Print summary
    fixer.print_summary()

    # Execute
    fixer.execute()

    if not args.dry_run:
        logger.info("\n" + "=" * 60)
        logger.info("NEXT STEPS")
        logger.info("=" * 60)
        logger.info("1. Update code references to databases:")
        logger.info("   - src/analytics/engine.py: default path should be 'src/analytics/market_data.duckdb'")
        logger.info("")
        logger.info("2. Update .gitignore:")
        logger.info("   - Add src/analytics/*.duckdb")
        logger.info("")
        logger.info("3. Test analytics:")
        logger.info("   python -c 'from src.analytics.engine import MarketAnalytics; ma = MarketAnalytics()'")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
