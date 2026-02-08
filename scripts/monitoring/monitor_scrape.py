#!/usr/bin/env python3
"""
Scrape Monitoring Tool
Monitors active scraping jobs and shows progress in real-time
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
import subprocess


def get_running_scrapes():
    """Check if scrape process is running."""
    try:
        # Check for Python processes running cli.py scrape
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'],
            capture_output=True,
            text=True
        )

        # Simple check - look for python processes (on Windows)
        if 'python.exe' in result.stdout:
            return True
        return False
    except Exception:
        # Fallback - assume running if recent log activity
        log_file = Path("src/observability/logs/carrefour_full_scrape.log")
        if log_file.exists():
            # Check if log was modified in last 5 minutes
            mod_time = datetime.fromtimestamp(log_file.stat().st_mtime)
            if datetime.now() - mod_time < timedelta(minutes=5):
                return True
        return False


def parse_log_progress(log_file: Path):
    """Parse log file to extract progress information."""
    if not log_file.exists():
        return None

    progress = {
        'status': 'unknown',
        'current_region': None,
        'products_discovered': 0,
        'batches_completed': 0,
        'validation_errors': 0,
        'http_404_errors': 0,
        'last_update': None,
    }

    try:
        # Read last 200 lines for recent activity
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            recent_lines = lines[-200:] if len(lines) > 200 else lines

        for line in recent_lines:
            # Extract key information
            if 'Discovered' in line and 'products' in line:
                # Pattern: "Discovered 65044 products"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.isdigit() and i + 1 < len(parts) and 'product' in parts[i + 1]:
                        progress['products_discovered'] = int(part)

            if 'Starting HTML-based scrape' in line or 'Scraping' in line:
                # Extract region
                if '/' in line:
                    region = line.split('/')[1].split(']')[0] if ']' in line else None
                    if region:
                        progress['current_region'] = region

            if 'Batch' in line and 'products' in line:
                progress['batches_completed'] += 1

            if 'validation' in line.lower() and 'failed' in line.lower():
                progress['validation_errors'] += 1

            if '404' in line:
                progress['http_404_errors'] += 1

            if 'Completed successfully' in line:
                progress['status'] = 'completed'
            elif 'Starting run' in line:
                progress['status'] = 'running'
            elif 'ERROR' in line and 'Run' in line and 'failed' in line:
                progress['status'] = 'failed'

        # Get last modification time
        progress['last_update'] = datetime.fromtimestamp(log_file.stat().st_mtime)

        return progress

    except Exception as e:
        print(f"Error parsing log: {e}")
        return None


def count_scraped_files():
    """Count Parquet files in bronze layer."""
    carrefour_path = Path("data/bronze/supermarket=carrefour")
    if not carrefour_path.exists():
        return 0, []

    parquet_files = list(carrefour_path.glob("**/*_full.parquet"))

    regions = {}
    for file in parquet_files:
        # Extract region from path
        parts = str(file).split('region=')
        if len(parts) > 1:
            region = parts[1].split('\\')[0].split('/')[0]
            size_mb = file.stat().st_size / 1024 / 1024
            regions[region] = regions.get(region, 0) + size_mb

    return len(parquet_files), regions


def estimate_completion(progress):
    """Estimate time to completion."""
    if not progress or progress['products_discovered'] == 0:
        return None

    # Assume 0.5s per product + overhead
    products_remaining = progress['products_discovered']
    time_per_product = 0.7  # seconds (including overhead, 404s, etc.)
    est_seconds = products_remaining * time_per_product

    return timedelta(seconds=int(est_seconds))


def format_timedelta(td):
    """Format timedelta for display."""
    if not td:
        return "Unknown"

    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if td.days > 0:
        return f"{td.days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m {seconds}s"


def print_dashboard():
    """Print monitoring dashboard."""
    print("\n" + "=" * 70)
    print("  🔍 CARREFOUR SCRAPE MONITOR")
    print("=" * 70 + "\n")

    # Check if running
    is_running = get_running_scrapes()
    status_icon = "🟢" if is_running else "🔴"
    print(f"{status_icon} Scrape Status: {'RUNNING' if is_running else 'STOPPED'}\n")

    # Parse log
    log_file = Path("src/observability/logs/carrefour_full_scrape.log")
    progress = parse_log_progress(log_file)

    if progress:
        print(f"📊 Progress:")
        print(f"  • Products discovered: {progress['products_discovered']:,}")
        print(f"  • Batches completed: {progress['batches_completed']:,}")
        print(f"  • Current region: {progress['current_region'] or 'N/A'}")
        print(f"  • Last update: {progress['last_update'].strftime('%Y-%m-%d %H:%M:%S') if progress['last_update'] else 'N/A'}")
        print(f"\n⚠️  Issues:")
        print(f"  • HTTP 404 errors: {progress['http_404_errors']:,} (inactive products)")
        print(f"  • Validation errors: {progress['validation_errors']:,}")

        # Estimate completion
        if is_running and progress['products_discovered'] > 0:
            eta = estimate_completion(progress)
            print(f"\n⏱️  Estimated completion: {format_timedelta(eta)}")

    # Count scraped files
    file_count, regions = count_scraped_files()
    print(f"\n📁 Output Files:")
    print(f"  • Total Parquet files: {file_count}")

    if regions:
        print(f"  • Regions completed:")
        for region, size_mb in sorted(regions.items()):
            print(f"    - {region}: {size_mb:.1f} MB")

    print("\n" + "-" * 70)
    print(f"📝 Log file: {log_file}")
    print(f"💾 Data path: data/bronze/supermarket=carrefour/")
    print("=" * 70 + "\n")


def tail_log(n_lines=20):
    """Show last N lines of log."""
    log_file = Path("src/observability/logs/carrefour_full_scrape.log")
    if not log_file.exists():
        print("❌ Log file not found")
        return

    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        recent = lines[-n_lines:] if len(lines) > n_lines else lines

    print("\n" + "=" * 70)
    print(f"  📄 LAST {n_lines} LOG LINES")
    print("=" * 70 + "\n")

    for line in recent:
        print(line.rstrip())

    print()


def main():
    """Main monitoring loop."""
    if len(sys.argv) > 1 and sys.argv[1] == "--tail":
        tail_log(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
        return

    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        # Watch mode - refresh every 30 seconds
        try:
            while True:
                print("\033[2J\033[H")  # Clear screen
                print_dashboard()
                print("Press Ctrl+C to stop watching...")
                time.sleep(30)
        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped.\n")
    else:
        # Single snapshot
        print_dashboard()
        print("\nUsage:")
        print("  python monitor_scrape.py           # Show current status")
        print("  python monitor_scrape.py --watch   # Auto-refresh every 30s")
        print("  python monitor_scrape.py --tail    # Show last 20 log lines")
        print("  python monitor_scrape.py --tail 50 # Show last 50 log lines\n")


if __name__ == "__main__":
    main()
