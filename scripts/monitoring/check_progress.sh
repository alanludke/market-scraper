#!/bin/bash
# Quick progress checker

echo "📊 Scrape Progress Check"
echo "========================"
echo ""

# Check if scrapers are running
if pgrep -f "cli.py scrape" > /dev/null; then
    echo "✅ Scrapers RUNNING"
    echo ""
    
    # Count Parquet files created
    echo "📁 Files Created:"
    bistek_files=$(find data/bronze/supermarket=bistek -name "*.parquet" 2>/dev/null | wc -l)
    fort_files=$(find data/bronze/supermarket=fort -name "*.parquet" 2>/dev/null | wc -l)
    giassi_files=$(find data/bronze/supermarket=giassi -name "*.parquet" 2>/dev/null | wc -l)
    
    echo "  - Bistek: $bistek_files files"
    echo "  - Fort: $fort_files files"
    echo "  - Giassi: $giassi_files files"
    echo "  - Total: $((bistek_files + fort_files + giassi_files)) files"
    echo ""
    
    # Log sizes
    echo "📋 Log Sizes:"
    [ -f data/logs/bistek.log ] && echo "  - bistek.log: $(du -h data/logs/bistek.log | cut -f1)"
    [ -f data/logs/fort.log ] && echo "  - fort.log: $(du -h data/logs/fort.log | cut -f1)"
    [ -f data/logs/giassi.log ] && echo "  - giassi.log: $(du -h data/logs/giassi.log | cut -f1)"
else
    echo "⏸️  Scrapers NOT RUNNING"
    echo ""
    echo "Check logs for completion:"
    echo "  tail -30 data/logs/bistek.log"
    echo "  tail -30 data/logs/fort.log"
    echo "  tail -30 data/logs/giassi.log"
fi
