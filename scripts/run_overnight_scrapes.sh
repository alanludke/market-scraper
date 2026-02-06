#!/bin/bash
# Overnight parallel scrapes - All stores, no limits
# Run with: bash run_overnight_scrapes.sh

cd /c/Users/alan.ludke_indicium/Documents/market_scraper

echo "🚀 Starting complete parallel scrapes at $(date)"
echo "=========================================="

# Run all 3 stores in parallel (no limits)
python cli.py scrape bistek &
PID_BISTEK=$!

python cli.py scrape fort &
PID_FORT=$!

python cli.py scrape giassi &
PID_GIASSI=$!

echo "Started scrapes:"
echo "  - Bistek (PID: $PID_BISTEK)"
echo "  - Fort (PID: $PID_FORT)"
echo "  - Giassi (PID: $PID_GIASSI)"

# Wait for all to complete
wait $PID_BISTEK
STATUS_BISTEK=$?

wait $PID_FORT
STATUS_FORT=$?

wait $PID_GIASSI
STATUS_GIASSI=$?

echo ""
echo "=========================================="
echo "🏁 All scrapes completed at $(date)"
echo "Results:"
echo "  - Bistek: $([ $STATUS_BISTEK -eq 0 ] && echo '✅ SUCCESS' || echo '❌ FAILED')"
echo "  - Fort: $([ $STATUS_FORT -eq 0 ] && echo '✅ SUCCESS' || echo '❌ FAILED')"
echo "  - Giassi: $([ $STATUS_GIASSI -eq 0 ] && echo '✅ SUCCESS' || echo '❌ FAILED')"
echo ""
echo "Check logs at:"
echo "  - data/logs/bistek.log"
echo "  - data/logs/fort.log"
echo "  - data/logs/giassi.log"
echo ""
echo "Check metrics at:"
echo "  - data/metrics/bistek_runs.duckdb"
echo "  - data/metrics/fort_runs.duckdb"
echo "  - data/metrics/giassi_runs.duckdb"
