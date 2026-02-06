"""
Streamlit Entry Point - Market Scraper Dashboard
==================================================

This file redirects to the main dashboard application.
The actual dashboard is in src/dashboard/app.py
"""

import sys
from pathlib import Path

# Add src to path so imports work
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import and run the main dashboard
from dashboard.app import main

if __name__ == "__main__":
    main()
