# Script PowerShell para deploy dos flows no Prefect Cloud

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Deploy Flows para Prefect Cloud" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar se está logado no Cloud
Write-Host "1. Verificando conexao com Prefect Cloud..." -ForegroundColor Cyan
$config = prefect config view
if ($config -notmatch "prefect.cloud") {
    Write-Host "ERRO: Nao esta conectado ao Prefect Cloud!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Execute primeiro: prefect cloud login" -ForegroundColor Yellow
    exit 1
}
Write-Host "Conectado ao Prefect Cloud" -ForegroundColor Green
Write-Host ""

# Deploy do flow principal (scraper diário com modo incremental)
Write-Host "2. Fazendo deploy do Daily Scraper Flow (INCREMENTAL)..." -ForegroundColor Cyan
prefect deploy src/orchestration/scraper_flow.py:daily_scraper_flow `
    --name daily-scraper-incremental `
    --pool market-scraper-pool `
    --cron "0 2 * * *" `
    --description "Daily incremental scraping (last 7 days) - 8-16x faster!" `
    --param use_incremental=true `
    --param incremental_days=7

if ($LASTEXITCODE -eq 0) {
    Write-Host "Daily Scraper (Incremental) deployed!" -ForegroundColor Green
} else {
    Write-Host "Erro no deploy do Daily Scraper (Incremental)" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Deploy do flow mensal (full catalog refresh)
Write-Host "3. Fazendo deploy do Monthly Full Scraper..." -ForegroundColor Cyan
prefect deploy src/orchestration/scraper_flow.py:daily_scraper_flow `
    --name monthly-scraper-full `
    --pool market-scraper-pool `
    --cron "0 3 1 * *" `
    --description "Monthly full catalog refresh (1st of month at 3 AM)" `
    --param use_incremental=false

if ($LASTEXITCODE -eq 0) {
    Write-Host "Monthly Scraper (Full) deployed!" -ForegroundColor Green
} else {
    Write-Host "Erro no deploy do Monthly Scraper (Full)" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Deploy do flow de delta sync (OpenFoodFacts)
Write-Host "4. Fazendo deploy do Delta Sync Flow..." -ForegroundColor Cyan
if (Test-Path "src/orchestration/delta_sync_flow.py") {
    prefect deploy src/orchestration/delta_sync_flow.py:daily_delta_sync_flow `
        --name daily-delta-sync `
        --pool market-scraper-pool `
        --cron "0 9 * * *" `
        --description "Daily OpenFoodFacts delta sync (9 AM)"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "Delta Sync Flow deployed!" -ForegroundColor Green
    } else {
        Write-Host "Delta Sync Flow failed (nao e critico)" -ForegroundColor Yellow
    }
} else {
    Write-Host "Delta Sync Flow nao encontrado (pulando)" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Deploy Completo!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Flows deployados:" -ForegroundColor Cyan
Write-Host "  1. daily-scraper-incremental (Todos os dias as 2 AM)" -ForegroundColor White
Write-Host "  2. monthly-scraper-full (Todo dia 1 as 3 AM)" -ForegroundColor White
Write-Host "  3. daily-delta-sync (Todos os dias as 9 AM)" -ForegroundColor White
Write-Host ""
Write-Host "Proximo passo:" -ForegroundColor Cyan
Write-Host "  Iniciar worker: prefect worker start --pool market-scraper-pool" -ForegroundColor White
Write-Host ""
Write-Host "Dashboard:" -ForegroundColor Cyan
Write-Host "  https://app.prefect.cloud" -ForegroundColor White
Write-Host ""
