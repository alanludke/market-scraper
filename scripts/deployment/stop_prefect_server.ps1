# Script para parar o servidor Prefect
# Uso: .\scripts\stop_prefect_server.ps1

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host "="*60 -ForegroundColor Cyan
Write-Host "  Parando Servidor Prefect" -ForegroundColor Red
Write-Host "="*60 -ForegroundColor Cyan
Write-Host ""

# Encontrar processos Prefect server
$processes = Get-Process | Where-Object { $_.ProcessName -eq "python" -or $_.ProcessName -eq "prefect" } |
    Where-Object { $_.CommandLine -like "*prefect*server*start*" -or $_.CommandLine -like "*uvicorn*" }

if ($processes) {
    Write-Host "🔍 Encontrados $($processes.Count) processo(s) Prefect:" -ForegroundColor Cyan
    foreach ($proc in $processes) {
        Write-Host "  - PID: $($proc.Id) | Memória: $([math]::Round($proc.WorkingSet/1MB, 2)) MB" -ForegroundColor White
    }
    Write-Host ""

    Write-Host "🛑 Parando processos..." -ForegroundColor Yellow
    $processes | Stop-Process -Force
    Start-Sleep -Seconds 2

    Write-Host "✅ Servidor Prefect parado com sucesso!" -ForegroundColor Green
} else {
    Write-Host "ℹ️  Nenhum servidor Prefect ativo encontrado" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "="*60 -ForegroundColor Cyan
Write-Host ""
