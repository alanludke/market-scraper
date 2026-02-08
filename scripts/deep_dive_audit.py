"""
Complete project deep-dive audit.

Identifies:
- Duplicate files/directories
- Files in wrong locations (violating colocation)
- Unused files
- Missing __init__.py files
- Database files in wrong places

Usage:
    python scripts/deep_dive_audit.py
"""

import os
from pathlib import Path
from collections import defaultdict
from loguru import logger

# Configure logger
logger.add(
    "data/logs/deep_dive_audit_{time}.log",
    rotation="10 MB",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)


class DeepDiveAuditor:
    """Complete project audit."""

    def __init__(self, root: Path):
        self.root = root
        self.issues = {
            "wrong_location": [],
            "duplicates": [],
            "unused": [],
            "missing_init": [],
            "database_files": [],
        }

    def audit(self) -> None:
        """Run complete audit."""
        logger.info("Starting deep-dive audit...\n")

        self.check_database_files()
        self.check_duplicates()
        self.check_colocation()
        self.check_unused_files()
        self.check_missing_init()

    def check_database_files(self) -> None:
        """Find all database files and verify their locations."""
        logger.info("🔍 Checking database files...")

        db_files = list(self.root.glob("**/*.duckdb"))
        db_files.extend(list(self.root.glob("**/*.db")))
        db_files.extend(list(self.root.glob("**/*.sqlite")))

        # Filter out .venv and archive
        db_files = [f for f in db_files if ".venv" not in str(f) and "archive" not in str(f)]

        for db_file in db_files:
            relative_path = db_file.relative_to(self.root)

            # Check location based on purpose
            if "analytics" in db_file.name or "market_data" in db_file.name:
                # Should be in src/analytics/
                if "src/analytics" not in str(db_file):
                    self.issues["database_files"].append({
                        "file": str(relative_path),
                        "current": str(db_file.parent),
                        "should_be": "src/analytics/",
                        "reason": "Analytics database should be colocated with analytics code"
                    })
            elif "metrics" in db_file.name or "runs" in db_file.name:
                # Should be in data/metrics/
                if "data/metrics" not in str(db_file):
                    self.issues["database_files"].append({
                        "file": str(relative_path),
                        "current": str(db_file.parent),
                        "should_be": "data/metrics/",
                        "reason": "Metrics database should be in data/metrics/"
                    })

        logger.info(f"  Found {len(db_files)} database files\n")

    def check_duplicates(self) -> None:
        """Find duplicate files or directories."""
        logger.info("🔍 Checking for duplicates...")

        # Check for duplicate Python module names
        py_files = defaultdict(list)
        for py_file in self.root.glob("**/*.py"):
            if ".venv" not in str(py_file) and "archive" not in str(py_file):
                py_files[py_file.name].append(py_file)

        # Report duplicates
        for filename, paths in py_files.items():
            if len(paths) > 1 and filename != "__init__.py":
                self.issues["duplicates"].append({
                    "file": filename,
                    "locations": [str(p.relative_to(self.root)) for p in paths]
                })

        logger.info(f"  Found {len([k for k, v in py_files.items() if len(v) > 1 and k != '__init__.py'])} duplicate files\n")

    def check_colocation(self) -> None:
        """Check if files follow colocation principle."""
        logger.info("🔍 Checking colocation principle...")

        # Define what should be colocated
        colocation_rules = {
            # Config files should be with their domain
            ".coveragerc": "tests/",
            "pytest.ini": "tests/",  # Already moved
            ".streamlit": "src/dashboard/",  # Already moved
            "prefect.yaml": "src/orchestration/",  # Already moved

            # Database files
            "market_data.duckdb": "src/analytics/",
            "analytics.duckdb": "src/analytics/",

            # DBT-related
            "dbt_project.yml": "src/transform/dbt_project/",
        }

        for pattern, expected_location in colocation_rules.items():
            files = list(self.root.glob(f"**/{pattern}"))
            files = [f for f in files if ".venv" not in str(f) and "archive" not in str(f)]

            for file in files:
                if expected_location not in str(file):
                    self.issues["wrong_location"].append({
                        "file": str(file.relative_to(self.root)),
                        "current": str(file.parent.relative_to(self.root)),
                        "should_be": expected_location,
                        "rule": "Colocation principle"
                    })

        logger.info(f"  Found {len(self.issues['wrong_location'])} files in wrong location\n")

    def check_unused_files(self) -> None:
        """Find potentially unused files."""
        logger.info("🔍 Checking for unused files...")

        # Files that might be unused (old patterns)
        suspicious_patterns = [
            "**/old_*.py",
            "**/backup_*.py",
            "**/temp_*.py",
            "**/test_*.txt",
            "**/*.pyc",
            "**/.DS_Store",
            "**/Thumbs.db",
        ]

        for pattern in suspicious_patterns:
            files = list(self.root.glob(pattern))
            files = [f for f in files if ".venv" not in str(f) and "archive" not in str(f)]

            for file in files:
                self.issues["unused"].append(str(file.relative_to(self.root)))

        logger.info(f"  Found {len(self.issues['unused'])} potentially unused files\n")

    def check_missing_init(self) -> None:
        """Find Python packages missing __init__.py."""
        logger.info("🔍 Checking for missing __init__.py files...")

        # Find all directories containing Python files
        python_dirs = set()
        for py_file in self.root.glob("**/*.py"):
            if ".venv" not in str(py_file) and "archive" not in str(py_file) and "__pycache__" not in str(py_file):
                python_dirs.add(py_file.parent)

        # Check if they have __init__.py
        for py_dir in python_dirs:
            init_file = py_dir / "__init__.py"
            if not init_file.exists() and py_dir.name not in ["scripts", "tests", "pages"]:
                # scripts/, tests/, pages/ don't need to be packages
                self.issues["missing_init"].append(str(py_dir.relative_to(self.root)))

        logger.info(f"  Found {len(self.issues['missing_init'])} directories missing __init__.py\n")

    def print_report(self) -> None:
        """Print detailed audit report."""
        logger.info("\n" + "=" * 80)
        logger.info("DEEP-DIVE AUDIT REPORT")
        logger.info("=" * 80)

        # Database files
        if self.issues["database_files"]:
            logger.info("\n🗄️  DATABASE FILES IN WRONG LOCATION:")
            for issue in self.issues["database_files"]:
                logger.info(f"\n  ❌ {issue['file']}")
                logger.info(f"     Current: {issue['current']}")
                logger.info(f"     Should be: {issue['should_be']}")
                logger.info(f"     Reason: {issue['reason']}")
        else:
            logger.info("\n✅ All database files are correctly located")

        # Duplicates
        if self.issues["duplicates"]:
            logger.info("\n📋 DUPLICATE FILES:")
            for issue in self.issues["duplicates"]:
                logger.info(f"\n  ⚠️  {issue['file']} exists in multiple locations:")
                for location in issue['locations']:
                    logger.info(f"     - {location}")
        else:
            logger.info("\n✅ No duplicate files found")

        # Wrong location
        if self.issues["wrong_location"]:
            logger.info("\n📍 FILES IN WRONG LOCATION (Colocation Violation):")
            for issue in self.issues["wrong_location"]:
                logger.info(f"\n  ❌ {issue['file']}")
                logger.info(f"     Current: {issue['current']}")
                logger.info(f"     Should be: {issue['should_be']}")
                logger.info(f"     Rule: {issue['rule']}")
        else:
            logger.info("\n✅ All files follow colocation principle")

        # Unused files
        if self.issues["unused"]:
            logger.info("\n🗑️  POTENTIALLY UNUSED FILES:")
            for file in self.issues["unused"]:
                logger.info(f"  ⚠️  {file}")
        else:
            logger.info("\n✅ No obviously unused files found")

        # Missing __init__.py
        if self.issues["missing_init"]:
            logger.info("\n📦 DIRECTORIES MISSING __init__.py:")
            for directory in self.issues["missing_init"]:
                logger.info(f"  ⚠️  {directory}")
        else:
            logger.info("\n✅ All Python packages have __init__.py")

        logger.info("\n" + "=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Database files in wrong location: {len(self.issues['database_files'])}")
        logger.info(f"Duplicate files: {len(self.issues['duplicates'])}")
        logger.info(f"Files in wrong location: {len(self.issues['wrong_location'])}")
        logger.info(f"Potentially unused files: {len(self.issues['unused'])}")
        logger.info(f"Missing __init__.py: {len(self.issues['missing_init'])}")
        logger.info("=" * 80)

        # Recommendations
        if any(self.issues.values()):
            logger.info("\n💡 RECOMMENDATIONS:")
            logger.info("1. Run: python scripts/fix_colocation_violations.py")
            logger.info("   (Will be created to fix all violations automatically)")
            logger.info("")
            logger.info("2. Review duplicate files and delete old versions")
            logger.info("")
            logger.info("3. Add missing __init__.py files")


def main():
    root = Path.cwd()
    auditor = DeepDiveAuditor(root)

    auditor.audit()
    auditor.print_report()


if __name__ == "__main__":
    main()
