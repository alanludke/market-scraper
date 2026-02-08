# Deploy para Prefect Cloud FREE TIER
# Usa Agents em vez de Work Pools

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Deploy para Prefect Cloud (Free Tier)" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar conexão
Write-Host "1. Verificando conexao com Prefect Cloud..." -ForegroundColor Cyan
$config = prefect config view
if ($config -notmatch "prefect.cloud") {
    Write-Host "ERRO: Nao conectado ao Prefect Cloud!" -ForegroundColor Red
    Write-Host "Execute: prefect cloud login" -ForegroundColor Yellow
    exit 1
}
Write-Host "Conectado ao Prefect Cloud (Free Tier)" -ForegroundColor Green
Write-Host ""

Write-Host "NOTA: Free Tier usa Agents (nao Work Pools)" -ForegroundColor Yellow
Write-Host "Isso e mais simples e funciona perfeitamente!" -ForegroundColor Yellow
Write-Host ""

# Deploy 1: Daily Scraper (Incremental)
Write-Host "2. Deploy: Daily Scraper (INCREMENTAL)..." -ForegroundColor Cyan
prefect deployment build src/orchestration/scraper_flow.py:daily_scraper_flow `
    --name daily-scraper-incremental `
    --schedule '{"cron": "0 2 * * *", "timezone": "America/Sao_Paulo"}' `
    --tag "scraper" --tag "incremental" --tag "daily" `
    --param use_incremental=true `
    --param incremental_days=7 `
    --output deployments/daily-scraper-incremental.yaml `
    --override

if ($LASTEXITCODE -eq 0) {
    prefect deployment apply deployments/daily-scraper-incremental.yaml
    Write-Host "Daily Scraper (Incremental) deployed!" -ForegroundColor Green
} else {
    Write-Host "Erro no deploy" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Deploy 2: Monthly Scraper (Full)
Write-Host "3. Deploy: Monthly Scraper (FULL)..." -ForegroundColor Cyan
prefect deployment build src/orchestration/scraper_flow.py:daily_scraper_flow `
    --name monthly-scraper-full `
    --schedule '{"cron": "0 3 1 * *", "timezone": "America/Sao_Paulo"}' `
    --tag "scraper" --tag "full" --tag "monthly" `
    --param use_incremental=false `
    --output deployments/monthly-scraper-full.yaml `
    --override

if ($LASTEXITCODE -eq 0) {
    prefect deployment apply deployments/monthly-scraper-full.yaml
    Write-Host "Monthly Scraper (Full) deployed!" -ForegroundColor Green
} else {
    Write-Host "Erro no deploy" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Deploy 3: Delta Sync (se existir)
Write-Host "4. Deploy: Delta Sync..." -ForegroundColor Cyan
if (Test-Path "src/orchestration/delta_sync_flow.py") {
    prefect deployment build src/orchestration/delta_sync_flow.py:daily_delta_sync_flow `
        --name daily-delta-sync `
        --schedule '{"cron": "0 9 * * *", "timezone": "America/Sao_Paulo"}' `
        --tag "enrichment" --tag "daily" `
        --output deployments/daily-delta-sync.yaml `
        --override

    if ($LASTEXITCODE -eq 0) {
        prefect deployment apply deployments/daily-delta-sync.yaml
        Write-Host "Delta Sync deployed!" -ForegroundColor Green
    }
} else {
    Write-Host "Delta Sync nao encontrado (pulando)" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Deploy Completo!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Flows deployados:" -ForegroundColor Cyan
Write-Host "  1. daily-scraper-incremental" -ForegroundColor White
Write-Host "     - Horario: 2 AM (horario de Brasilia)" -ForegroundColor Gray
Write-Host "     - Modo: Incremental (7 dias)" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. monthly-scraper-full" -ForegroundColor White
Write-Host "     - Horario: 3 AM dia 1 (horario de Brasilia)" -ForegroundColor Gray
Write-Host "     - Modo: Full catalog" -ForegroundColor Gray
Write-Host ""
Write-Host "Proximo passo:" -ForegroundColor Cyan
Write-Host "  Iniciar agent: prefect agent start -q default" -ForegroundColor White
Write-Host ""
Write-Host "Dashboard:" -ForegroundColor Cyan
Write-Host "  https://app.prefect.cloud" -ForegroundColor White
Write-Host ""
