"""
Utility script to manage scraper URL cache.

The cache stores URLs that returned 404 to avoid re-checking them on every run.
Cache entries automatically expire after N days (default: 7 days).

Usage:
    # View cache stats
    python scripts/manage_cache.py stats carrefour

    # Clear all cache (force re-check all products)
    python scripts/manage_cache.py clear carrefour

    # Clean expired entries only
    python scripts/manage_cache.py clean carrefour

    # View cached URLs
    python scripts/manage_cache.py list carrefour
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_cache(store_name: str) -> list:
    """Load cache entries from file."""
    cache_file = Path(f"data/cache/{store_name}_failed_urls.jsonl")

    if not cache_file.exists():
        return []

    entries = []
    with open(cache_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return entries


def save_cache(store_name: str, entries: list):
    """Save cache entries to file."""
    cache_file = Path(f"data/cache/{store_name}_failed_urls.jsonl")
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    with open(cache_file, 'w', encoding='utf-8') as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def cmd_stats(store_name: str, ttl_days: int = 7):
    """Show cache statistics."""
    entries = load_cache(store_name)

    if not entries:
        print(f"No cache entries found for {store_name}")
        return

    cutoff_date = datetime.now() - timedelta(days=ttl_days)

    valid_entries = [
        e for e in entries
        if datetime.fromisoformat(e['failed_at']) >= cutoff_date
    ]
    expired_entries = len(entries) - len(valid_entries)

    print(f"=" * 70)
    print(f"Cache Statistics: {store_name}")
    print(f"=" * 70)
    print(f"Total entries:     {len(entries):,}")
    print(f"Valid entries:     {len(valid_entries):,} (within {ttl_days} days)")
    print(f"Expired entries:   {expired_entries:,}")
    print()

    if valid_entries:
        # Show age distribution
        ages = [
            (datetime.now() - datetime.fromisoformat(e['failed_at'])).days
            for e in valid_entries
        ]

        print(f"Age distribution of valid entries:")
        print(f"  0-1 days:   {sum(1 for a in ages if a <= 1):,}")
        print(f"  2-3 days:   {sum(1 for a in ages if 2 <= a <= 3):,}")
        print(f"  4-7 days:   {sum(1 for a in ages if 4 <= a <= 7):,}")
        print(f"  > 7 days:   {sum(1 for a in ages if a > 7):,}")
        print()

        # Show oldest and newest
        oldest = max(valid_entries, key=lambda e: e['failed_at'])
        newest = min(valid_entries, key=lambda e: e['failed_at'])

        oldest_age = (datetime.now() - datetime.fromisoformat(oldest['failed_at'])).days
        newest_age = (datetime.now() - datetime.fromisoformat(newest['failed_at'])).days

        print(f"Oldest entry: {oldest_age} days ago")
        print(f"Newest entry: {newest_age} days ago")


def cmd_clear(store_name: str):
    """Clear all cache entries."""
    cache_file = Path(f"data/cache/{store_name}_failed_urls.jsonl")

    if not cache_file.exists():
        print(f"No cache file found for {store_name}")
        return

    entries = load_cache(store_name)
    count = len(entries)

    cache_file.unlink()
    print(f"✓ Cache cleared: {count:,} entries deleted")
    print(f"All products will be re-checked on next scrape")


def cmd_clean(store_name: str, ttl_days: int = 7):
    """Remove expired entries from cache."""
    entries = load_cache(store_name)

    if not entries:
        print(f"No cache entries found for {store_name}")
        return

    cutoff_date = datetime.now() - timedelta(days=ttl_days)

    valid_entries = [
        e for e in entries
        if datetime.fromisoformat(e['failed_at']) >= cutoff_date
    ]

    expired_count = len(entries) - len(valid_entries)

    if expired_count == 0:
        print(f"No expired entries found (all within {ttl_days} days)")
        return

    save_cache(store_name, valid_entries)
    print(f"✓ Cleaned cache: {expired_count:,} expired entries removed")
    print(f"✓ Remaining: {len(valid_entries):,} valid entries")


def cmd_list(store_name: str, limit: int = 20):
    """List cached URLs."""
    entries = load_cache(store_name)

    if not entries:
        print(f"No cache entries found for {store_name}")
        return

    # Sort by most recent first
    entries.sort(key=lambda e: e['failed_at'], reverse=True)

    print(f"=" * 70)
    print(f"Cached Failed URLs: {store_name} (showing {min(limit, len(entries))} of {len(entries)})")
    print(f"=" * 70)

    for entry in entries[:limit]:
        failed_at = datetime.fromisoformat(entry['failed_at'])
        age = (datetime.now() - failed_at).days

        print(f"{age:>3}d ago | {entry['url']}")

    if len(entries) > limit:
        print()
        print(f"... and {len(entries) - limit:,} more entries")
        print(f"Use --limit to see more (e.g., python scripts/manage_cache.py list {store_name} --limit 100)")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()
    store_name = sys.argv[2].lower()

    # Optional TTL parameter
    ttl_days = 7
    if '--ttl' in sys.argv:
        ttl_idx = sys.argv.index('--ttl')
        if ttl_idx + 1 < len(sys.argv):
            ttl_days = int(sys.argv[ttl_idx + 1])

    # Optional limit parameter
    limit = 20
    if '--limit' in sys.argv:
        limit_idx = sys.argv.index('--limit')
        if limit_idx + 1 < len(sys.argv):
            limit = int(sys.argv[limit_idx + 1])

    if command == 'stats':
        cmd_stats(store_name, ttl_days)
    elif command == 'clear':
        cmd_clear(store_name)
    elif command == 'clean':
        cmd_clean(store_name, ttl_days)
    elif command == 'list':
        cmd_list(store_name, limit)
    else:
        print(f"Unknown command: {command}")
        print("Available commands: stats, clear, clean, list")
        sys.exit(1)


if __name__ == "__main__":
    main()
