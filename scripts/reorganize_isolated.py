"""
Reorganize configuration files following strict colocation principle.

Move configuration files to their respective domains:
- .prefectignore → src/orchestration/.prefectignore
- prefect.yaml → src/orchestration/prefect.yaml
- .streamlit/ → src/dashboard/.streamlit/
- pytest.ini → tests/pytest.ini
- .github/ → Keep at root (repository-level)

Usage:
    python scripts/reorganize_isolated.py --dry-run  # Preview
    python scripts/reorganize_isolated.py            # Execute
"""

import argparse
import shutil
from pathlib import Path
from loguru import logger

# Configure logger
logger.add(
    "data/logs/reorganize_isolated_{time}.log",
    rotation="10 MB",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)


class IsolatedReorganizer:
    """Reorganize configs to isolate each domain."""

    def __init__(self, root: Path, dry_run: bool = False):
        self.root = root
        self.dry_run = dry_run
        self.moves = []
        self.copies = []  # For files that need to be copied (not moved)

    def plan_reorganization(self) -> None:
        """Plan isolated reorganization."""

        # 1. Prefect configs → src/orchestration/
        prefectignore_src = self.root / ".prefectignore"
        prefectignore_dst = self.root / "src/orchestration/.prefectignore"
        if prefectignore_src.exists():
            self.moves.append((
                prefectignore_src,
                prefectignore_dst,
                "Prefect ignore patterns"
            ))

        prefect_yaml_src = self.root / "prefect.yaml"
        prefect_yaml_dst = self.root / "src/orchestration/prefect.yaml"
        if prefect_yaml_src.exists():
            self.moves.append((
                prefect_yaml_src,
                prefect_yaml_dst,
                "Prefect deployment config"
            ))

        # 2. Streamlit config → src/dashboard/
        streamlit_src = self.root / ".streamlit"
        streamlit_dst = self.root / "src/dashboard/.streamlit"
        if streamlit_src.exists():
            self.moves.append((
                streamlit_src,
                streamlit_dst,
                "Streamlit configuration"
            ))

        # 3. Pytest config → tests/
        pytest_src = self.root / "pytest.ini"
        pytest_dst = self.root / "tests/pytest.ini"
        if pytest_src.exists():
            self.moves.append((
                pytest_src,
                pytest_dst,
                "Pytest configuration"
            ))

    def execute(self) -> None:
        """Execute the reorganization."""
        logger.info("Starting isolated reorganization (strict colocation)...")

        if not self.moves:
            logger.warning("No files to move (already organized or missing)")
            return

        logger.info(f"\n📦 Moving {len(self.moves)} configuration files...\n")

        for source, destination, description in self.moves:
            if not source.exists():
                logger.warning(f"⚠️  Source not found (skipping): {source}")
                continue

            if self.dry_run:
                logger.info(f"[DRY RUN] Would move: {source.name} → {destination}")
                logger.info(f"  {description}")
            else:
                # Create destination parent
                destination.parent.mkdir(parents=True, exist_ok=True)

                # Move file/directory
                shutil.move(str(source), str(destination))
                logger.info(f"✓ Moved: {source.name} → {destination}")
                logger.info(f"  {description}")

        logger.info("\n✅ Isolated reorganization complete!")

        if self.dry_run:
            logger.info("\nℹ️  This was a DRY RUN - no changes were made")
            logger.info("Run without --dry-run to execute the reorganization")

    def print_summary(self) -> None:
        """Print reorganization summary."""
        logger.info("\n" + "=" * 60)
        logger.info("ISOLATED REORGANIZATION PLAN")
        logger.info("=" * 60)
        logger.info("Principle: Each domain owns its configuration")
        logger.info("")
        for source, destination, description in self.moves:
            logger.info(f"• {source.name}")
            logger.info(f"  → {destination}")
            logger.info(f"  {description}")
            logger.info("")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Reorganize configs following strict colocation"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without executing"
    )

    args = parser.parse_args()

    # Initialize reorganizer
    root = Path.cwd()
    reorganizer = IsolatedReorganizer(root=root, dry_run=args.dry_run)

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
        logger.info("1. Update Prefect commands:")
        logger.info("   cd src/orchestration && prefect deploy")
        logger.info("")
        logger.info("2. Update Streamlit command:")
        logger.info("   streamlit run src/dashboard/app.py")
        logger.info("   (Streamlit will find .streamlit/ in src/dashboard/)")
        logger.info("")
        logger.info("3. Update pytest command:")
        logger.info("   pytest  # Will find tests/pytest.ini automatically")
        logger.info("")
        logger.info("4. Update CI/CD workflows:")
        logger.info("   Update paths in .github/workflows/*.yml")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
