# Script para iniciar o servidor Prefect em background no Windows
# Uso: .\scripts\start_prefect_server.ps1

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host "="*60 -ForegroundColor Cyan
Write-Host "  Iniciando Servidor Prefect" -ForegroundColor Green
Write-Host "="*60 -ForegroundColor Cyan
Write-Host ""

# Verificar se já está rodando
$existingProcess = Get-Process -Name "prefect" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*server start*" }
if ($existingProcess) {
    Write-Host "⚠️  Servidor Prefect já está rodando (PID: $($existingProcess.Id))" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Para parar o servidor:" -ForegroundColor Cyan
    Write-Host "  Stop-Process -Id $($existingProcess.Id)" -ForegroundColor White
    exit 0
}

# Iniciar servidor em background
Write-Host "🚀 Iniciando servidor Prefect em background..." -ForegroundColor Cyan

$logFile = "data/logs/prefect_server.log"
$errorFile = "data/logs/prefect_server_error.log"

# Criar diretório de logs se não existir
New-Item -ItemType Directory -Force -Path "data/logs" | Out-Null

# Iniciar processo em background
$process = Start-Process -FilePath "prefect" `
    -ArgumentList "server start" `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError $errorFile `
    -WindowStyle Hidden `
    -PassThru

Write-Host "✅ Servidor iniciado!" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Informações:" -ForegroundColor Cyan
Write-Host "  PID: $($process.Id)" -ForegroundColor White
Write-Host "  Dashboard: http://127.0.0.1:4200" -ForegroundColor White
Write-Host "  Logs: $logFile" -ForegroundColor White
Write-Host "  Errors: $errorFile" -ForegroundColor White
Write-Host ""
Write-Host "⏳ Aguardando servidor inicializar (10 segundos)..." -ForegroundColor Cyan
Start-Sleep -Seconds 10

# Verificar se está rodando
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:4200/api/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✅ Servidor está ONLINE e respondendo!" -ForegroundColor Green
    Write-Host ""
    Write-Host "🎯 Próximos passos:" -ForegroundColor Cyan
    Write-Host "  1. Acesse o dashboard: http://127.0.0.1:4200" -ForegroundColor White
    Write-Host "  2. Inicie um worker: prefect worker start --pool market-scraper-pool" -ForegroundColor White
    Write-Host "  3. Execute um flow: python src/orchestration/scraper_flow.py" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host "⚠️  Servidor iniciou mas ainda não está respondendo" -ForegroundColor Yellow
    Write-Host "   Aguarde mais alguns segundos e tente: http://127.0.0.1:4200" -ForegroundColor White
    Write-Host ""
    Write-Host "   Verifique os logs em: $logFile" -ForegroundColor White
}

Write-Host "="*60 -ForegroundColor Cyan
Write-Host ""
