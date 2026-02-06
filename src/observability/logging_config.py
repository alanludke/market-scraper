"""
Logging configuration using Loguru for structured, rotating logs.

Features:
- JSON serialization for production logs
- Colored console output for development
- Automatic rotation (10MB per file, 30 days retention)
- Correlation IDs via context binding
"""

from loguru import logger
import sys
from pathlib import Path


def setup_logging(run_id: str = None, store: str = None, region: str = None, verbose: bool = False):
    """
    Configure Loguru logger with console and file handlers.

    Args:
        run_id: Unique run identifier for correlation
        store: Store name (bistek, fort, giassi) - creates per-store log file for parallel execution
        region: Region key
        verbose: If True, set console level to DEBUG

    Returns:
        Configured logger with context bindings

    Note:
        Using per-store log files (e.g., bistek.log, fort.log) instead of a shared app.log
        prevents file rotation conflicts when running multiple scrapers in parallel.
    """
    # Remove default handler
    logger.remove()

    # Console handler: human-readable, colorido
    console_level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stdout,
        level=console_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        colorize=True,
    )

    # File handler: JSON, rotating
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Use per-store log file for parallel execution (avoids rotation conflicts)
    log_file = f"{store}.log" if store else "app.log"

    logger.add(
        log_dir / log_file,
        level="DEBUG",
        format="{time} {level} {message}",
        rotation="10 MB",          # Rotate when file reaches 10MB
        retention="30 days",        # Keep logs for 30 days
        serialize=True,             # JSON output
        enqueue=True,               # Thread-safe
    )

    # Bind context (will appear in all subsequent logs)
    context_logger = logger.bind(
        run_id=run_id or "unknown",
        store=store or "unknown",
        region=region or "unknown"
    )

    return context_logger


def get_logger():
    """Get the current logger instance (for modules that import after setup)."""
    return logger
