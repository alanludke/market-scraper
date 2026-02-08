#!/bin/bash
# Script para deploy dos flows no Prefect Cloud

echo "=========================================="
echo "  Deploy Flows para Prefect Cloud"
echo "=========================================="
echo ""

# Verificar se está logado no Cloud
echo "1. Verificando conexão com Prefect Cloud..."
if ! prefect config view | grep -q "prefect.cloud"; then
    echo "❌ ERRO: Não está conectado ao Prefect Cloud!"
    echo ""
    echo "Execute primeiro: prefect cloud login"
    exit 1
fi
echo "✅ Conectado ao Prefect Cloud"
echo ""

# Deploy do flow principal (scraper diário com modo incremental)
echo "2. Fazendo deploy do Daily Scraper Flow (INCREMENTAL)..."
prefect deploy src/orchestration/scraper_flow.py:daily_scraper_flow \
    --name daily-scraper-incremental \
    --pool market-scraper-pool \
    --cron "0 2 * * *" \
    --description "Daily incremental scraping (last 7 days) - 8-16x faster!" \
    --param use_incremental=true \
    --param incremental_days=7

if [ $? -eq 0 ]; then
    echo "✅ Daily Scraper (Incremental) deployed!"
else
    echo "❌ Erro no deploy do Daily Scraper (Incremental)"
    exit 1
fi
echo ""

# Deploy do flow mensal (full catalog refresh)
echo "3. Fazendo deploy do Monthly Full Scraper..."
prefect deploy src/orchestration/scraper_flow.py:daily_scraper_flow \
    --name monthly-scraper-full \
    --pool market-scraper-pool \
    --cron "0 3 1 * *" \
    --description "Monthly full catalog refresh (1st of month at 3 AM)" \
    --param use_incremental=false

if [ $? -eq 0 ]; then
    echo "✅ Monthly Scraper (Full) deployed!"
else
    echo "❌ Erro no deploy do Monthly Scraper (Full)"
    exit 1
fi
echo ""

# Deploy do flow de delta sync (OpenFoodFacts)
echo "4. Fazendo deploy do Delta Sync Flow..."
if [ -f "src/orchestration/delta_sync_flow.py" ]; then
    prefect deploy src/orchestration/delta_sync_flow.py:daily_delta_sync_flow \
        --name daily-delta-sync \
        --pool market-scraper-pool \
        --cron "0 9 * * *" \
        --description "Daily OpenFoodFacts delta sync (9 AM)"

    if [ $? -eq 0 ]; then
        echo "✅ Delta Sync Flow deployed!"
    else
        echo "⚠️  Delta Sync Flow failed (não é crítico)"
    fi
else
    echo "ℹ️  Delta Sync Flow não encontrado (pulando)"
fi
echo ""

echo "=========================================="
echo "  ✅ Deploy Completo!"
echo "=========================================="
echo ""
echo "📊 Flows deployados:"
echo "  1. daily-scraper-incremental (Todos os dias às 2 AM)"
echo "  2. monthly-scraper-full (Todo dia 1 às 3 AM)"
echo "  3. daily-delta-sync (Todos os dias às 9 AM)"
echo ""
echo "🎯 Próximo passo:"
echo "  Iniciar worker: prefect worker start --pool market-scraper-pool"
echo ""
echo "🌐 Dashboard:"
echo "  https://app.prefect.cloud"
echo ""
