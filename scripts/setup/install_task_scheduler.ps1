# ============================================================================
# Install Task Scheduler - Market Scraper Delta Sync
# ============================================================================
# Execute como Administrador: Right-click → Run as Administrator
# ============================================================================

$ErrorActionPreference = "Stop"

Write-Host "`n===================================================" -ForegroundColor Cyan
Write-Host "  Market Scraper - Task Scheduler Setup" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

# Detectar diretório do projeto
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Write-Host "`nProject Root: $ProjectRoot" -ForegroundColor Yellow

# Verificar se scripts existem
$BatchScript = Join-Path $ProjectRoot "scripts\daily_delta_sync.bat"
$PSScript = Join-Path $ProjectRoot "scripts\daily_delta_sync.ps1"

if (-not (Test-Path $BatchScript)) {
    Write-Host "`n[ERROR] Script não encontrado: $BatchScript" -ForegroundColor Red
    Write-Host "Certifique-se de estar executando de dentro do projeto market_scraper" -ForegroundColor Red
    exit 1
}

Write-Host "`n[1/5] Scripts encontrados:" -ForegroundColor Green
Write-Host "  - Batch: $BatchScript" -ForegroundColor Gray
Write-Host "  - PowerShell: $PSScript" -ForegroundColor Gray

# Perguntar qual script usar
Write-Host "`n[2/5] Escolha o script para automação:" -ForegroundColor Yellow
Write-Host "  1 - Batch (simples, compatível)" -ForegroundColor White
Write-Host "  2 - PowerShell (avançado, com email)" -ForegroundColor White
$Choice = Read-Host "`nEscolha (1 ou 2)"

if ($Choice -eq "1") {
    $ScriptPath = $BatchScript
    $ScriptType = "batch"
    $Executable = "cmd.exe"
    $Arguments = "/c `"$ScriptPath`""
} elseif ($Choice -eq "2") {
    $ScriptPath = $PSScript
    $ScriptType = "powershell"
    $Executable = "powershell.exe"
    $Arguments = "-ExecutionPolicy Bypass -File `"$ScriptPath`""
} else {
    Write-Host "`n[ERROR] Escolha inválida. Execute novamente." -ForegroundColor Red
    exit 1
}

Write-Host "`n[3/5] Configurando Task Scheduler..." -ForegroundColor Yellow

# Configurações da tarefa
$TaskName = "MarketScraperDeltaSync"
$Description = "Daily OpenFoodFacts delta sync for Market Scraper EAN enrichment"

# Criar ação
$Action = New-ScheduledTaskAction `
    -Execute $Executable `
    -Argument $Arguments `
    -WorkingDirectory $ProjectRoot

# Criar trigger (diário às 2:00 AM)
$Trigger = New-ScheduledTaskTrigger -Daily -At 2:00AM

# Configurações
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 10) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -Priority 5

# Criar principal (executar com seu usuário)
$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Highest

try {
    # Verificar se tarefa já existe
    $ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

    if ($ExistingTask) {
        Write-Host "`n[WARNING] Tarefa '$TaskName' já existe!" -ForegroundColor Yellow
        $Overwrite = Read-Host "Deseja substituir? (s/n)"

        if ($Overwrite -ne "s") {
            Write-Host "`n[CANCELLED] Instalação cancelada." -ForegroundColor Yellow
            exit 0
        }

        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "  Tarefa antiga removida." -ForegroundColor Gray
    }

    # Registrar nova tarefa
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description $Description | Out-Null

    Write-Host "`n[4/5] Tarefa criada com sucesso!" -ForegroundColor Green

    # Resumo da configuração
    Write-Host "`n===================================================" -ForegroundColor Cyan
    Write-Host "  CONFIGURAÇÃO" -ForegroundColor Cyan
    Write-Host "===================================================" -ForegroundColor Cyan
    Write-Host "  Nome:           $TaskName" -ForegroundColor White
    Write-Host "  Script:         $ScriptType" -ForegroundColor White
    Write-Host "  Horário:        Diário às 2:00 AM" -ForegroundColor White
    Write-Host "  Working Dir:    $ProjectRoot" -ForegroundColor White
    Write-Host "  Retry:          3x a cada 10 minutos" -ForegroundColor White
    Write-Host "  Timeout:        2 horas" -ForegroundColor White
    Write-Host "  Usuário:        $env:USERNAME" -ForegroundColor White
    Write-Host "===================================================" -ForegroundColor Cyan

    # Perguntar se quer testar agora
    Write-Host "`n[5/5] Deseja executar um teste agora?" -ForegroundColor Yellow
    $Test = Read-Host "(s/n)"

    if ($Test -eq "s") {
        Write-Host "`nExecutando teste..." -ForegroundColor Yellow
        Start-ScheduledTask -TaskName $TaskName

        Write-Host "`nTarefa iniciada! Aguardando 5 segundos..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5

        # Verificar status
        $TaskInfo = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host "`nStatus: $($TaskInfo.LastTaskResult)" -ForegroundColor $(if ($TaskInfo.LastTaskResult -eq 0) { "Green" } else { "Red" })

        Write-Host "`nVerifique o log em:" -ForegroundColor Cyan
        $LogDate = Get-Date -Format "yyyyMMdd"
        Write-Host "  $ProjectRoot\logs\delta_sync_$LogDate.log" -ForegroundColor White
    }

    # Comandos úteis
    Write-Host "`n===================================================" -ForegroundColor Cyan
    Write-Host "  COMANDOS ÚTEIS" -ForegroundColor Cyan
    Write-Host "===================================================" -ForegroundColor Cyan
    Write-Host "`nExecutar manualmente:" -ForegroundColor Yellow
    Write-Host "  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White

    Write-Host "`nVerificar status:" -ForegroundColor Yellow
    Write-Host "  Get-ScheduledTaskInfo -TaskName '$TaskName'" -ForegroundColor White

    Write-Host "`nAbrir Task Scheduler GUI:" -ForegroundColor Yellow
    Write-Host "  taskschd.msc" -ForegroundColor White

    Write-Host "`nDesabilitar/Habilitar:" -ForegroundColor Yellow
    Write-Host "  Disable-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
    Write-Host "  Enable-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White

    Write-Host "`nRemover tarefa:" -ForegroundColor Yellow
    Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor White

    Write-Host "`n===================================================" -ForegroundColor Cyan
    Write-Host "  INSTALAÇÃO CONCLUÍDA!" -ForegroundColor Green
    Write-Host "===================================================" -ForegroundColor Cyan
    Write-Host "`nA tarefa será executada automaticamente às 2:00 AM todos os dias." -ForegroundColor White
    Write-Host "Logs salvos em: $ProjectRoot\logs\delta_sync_YYYYMMDD.log`n" -ForegroundColor White

} catch {
    Write-Host "`n[ERROR] Falha ao criar tarefa:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "`nCertifique-se de estar executando como Administrador!" -ForegroundColor Yellow
    exit 1
}
