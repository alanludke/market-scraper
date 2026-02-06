"""
DEPRECATED: This module is deprecated. Please use src.ingest.scrapers instead.

The legacy src.scrapers module lacks proper logging, metrics, and error handling.
The new implementation in src.ingest.scrapers provides:
- Structured logging with Loguru (correlation IDs, JSON output)
- Operational metrics tracked in DuckDB (runs.duckdb)
- Parquet output (35x faster than JSONL)
- Proper exception handling (no silent failures)

This module will be removed in a future version.
"""

import warnings

warnings.warn(
    "src.scrapers is deprecated. Use src.ingest.scrapers instead. "
    "This module will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2,
)

from .vtex import VTEXScraper

SCRAPER_REGISTRY = {
    "vtex": VTEXScraper,
}
