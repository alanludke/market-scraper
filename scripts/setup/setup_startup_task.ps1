# Script para configurar execução automática ao ligar o PC
# Cria tarefa no Windows Task Scheduler

$projectPath = "C:\Users\alan.ludke_indicium\Documents\market_scraper"
$pythonPath = (Get-Command python).Path

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Configurar Scraper para Iniciar ao Ligar" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Tarefa 1: Scraping Incremental ao Ligar
Write-Host "1. Criando tarefa: Market Scraper - Startup" -ForegroundColor Cyan

$action = New-ScheduledTaskAction `
    -Execute $pythonPath `
    -Argument "run_scraper_standalone.py" `
    -WorkingDirectory $projectPath

$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = "PT5M"  # Aguarda 5 minutos após ligar (para rede estabilizar)

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
        -TaskName "Market Scraper - Startup (Incremental)" `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "Executa scraping incremental 5 minutos após ligar o PC" `
        -Force

    Write-Host "Tarefa criada com sucesso!" -ForegroundColor Green
} catch {
    Write-Host "Erro ao criar tarefa: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Configuracao Completa!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Tarefa criada:" -ForegroundColor Cyan
Write-Host "  Nome: Market Scraper - Startup (Incremental)" -ForegroundColor White
Write-Host "  Trigger: Ao ligar o PC (delay de 5 minutos)" -ForegroundColor White
Write-Host "  Modo: Incremental (ultimos 7 dias)" -ForegroundColor White
Write-Host "  Tempo estimado: 30-60 minutos" -ForegroundColor White
Write-Host ""
Write-Host "Para gerenciar:" -ForegroundColor Cyan
Write-Host "  1. Abra: Agendador de Tarefas (taskschd.msc)" -ForegroundColor White
Write-Host "  2. Procure: Market Scraper - Startup" -ForegroundColor White
Write-Host ""
Write-Host "Para testar agora:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName 'Market Scraper - Startup (Incremental)'" -ForegroundColor White
Write-Host ""
Write-Host "Para desabilitar:" -ForegroundColor Cyan
Write-Host "  Disable-ScheduledTask -TaskName 'Market Scraper - Startup (Incremental)'" -ForegroundColor White
Write-Host ""
Write-Host "Para remover:" -ForegroundColor Cyan
Write-Host "  Unregister-ScheduledTask -TaskName 'Market Scraper - Startup (Incremental)'" -ForegroundColor White
Write-Host ""