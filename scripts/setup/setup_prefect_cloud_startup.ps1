# Setup: Prefect Cloud runner ao ligar o PC

$projectPath = "C:\Users\alan.ludke_indicium\Documents\market_scraper"
$pythonPath = (Get-Command python).Path

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Configurar Prefect Cloud Startup" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Criar tarefa que inicia o Prefect Cloud serve
$action = New-ScheduledTaskAction `
    -Execute $pythonPath `
    -Argument "prefect_cloud_runner.py --serve" `
    -WorkingDirectory $projectPath

$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = "PT2M"  # 2 minutos após ligar

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

try {
    Register-ScheduledTask `
        -TaskName "Prefect Cloud - Market Scraper" `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "Conecta ao Prefect Cloud e aguarda execucoes agendadas" `
        -Force

    Write-Host "Tarefa criada!" -ForegroundColor Green
} catch {
    Write-Host "Erro: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Configuracao Completa!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Tarefa criada:" -ForegroundColor Cyan
Write-Host "  Nome: Prefect Cloud - Market Scraper" -ForegroundColor White
Write-Host "  Trigger: Ao ligar (aguarda 2 min)" -ForegroundColor White
Write-Host "  Acao: Conecta ao Prefect Cloud" -ForegroundColor White
Write-Host ""
Write-Host "Dashboard:" -ForegroundColor Cyan
Write-Host "  https://app.prefect.cloud" -ForegroundColor White
Write-Host ""
Write-Host "Para testar agora:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName 'Prefect Cloud - Market Scraper'" -ForegroundColor White
Write-Host ""