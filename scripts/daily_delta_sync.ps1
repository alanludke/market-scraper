# ============================================================================
# Daily Delta Sync - OpenFoodFacts Incremental Updates (PowerShell)
# ============================================================================
#
# This script:
# 1. Runs OpenFoodFacts delta sync to update EAN data
# 2. Updates DBT models (dim_ean)
# 3. Logs execution results
# 4. Sends email notification (optional)
#
# Schedule: Daily at 2:00 AM (via Task Scheduler)
# ============================================================================

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$LogDate = Get-Date -Format "yyyyMMdd"
$LogFile = Join-Path $ProjectRoot "logs\delta_sync_$LogDate.log"

function Write-Log {
    param([string]$Message)
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] $Message"
    Write-Host $LogMessage
    Add-Content -Path $LogFile -Value $LogMessage
}

Write-Log "Starting daily delta sync..."

# Change to project directory
Set-Location $ProjectRoot

# Activate virtual environment (if using one)
# & ".\venv\Scripts\Activate.ps1"

# Run delta sync
Write-Log "Running delta-sync..."
$DeltaSyncOutput = & python cli_enrich.py delta-sync 2>&1
$DeltaSyncExitCode = $LASTEXITCODE

# Log output
$DeltaSyncOutput | ForEach-Object { Write-Log $_ }

if ($DeltaSyncExitCode -eq 0) {
    Write-Log "Delta sync completed successfully"

    # Update DBT models
    Write-Log "Updating DBT models..."
    Set-Location "src\transform\dbt_project"

    $DbtOutput = & dbt run --select stg_openfoodfacts__products dim_ean 2>&1
    $DbtExitCode = $LASTEXITCODE

    # Log DBT output
    $DbtOutput | ForEach-Object { Write-Log $_ }

    if ($DbtExitCode -eq 0) {
        Write-Log "DBT update completed successfully"
        $Status = "SUCCESS"
    } else {
        Write-Log "ERROR: DBT update failed with code $DbtExitCode"
        $Status = "DBT_FAILED"
    }

    Set-Location $ProjectRoot
} else {
    Write-Log "ERROR: Delta sync failed with code $DeltaSyncExitCode"
    $Status = "SYNC_FAILED"
}

Write-Log "Daily delta sync finished with status: $Status"

# Optional: Send email notification
if ($env:SMTP_ENABLED -eq "true") {
    $EmailParams = @{
        From = $env:SMTP_FROM
        To = $env:SMTP_TO
        Subject = "Market Scraper - Delta Sync $Status"
        Body = Get-Content $LogFile -Raw
        SmtpServer = $env:SMTP_SERVER
        Port = $env:SMTP_PORT
        UseSsl = $true
        Credential = New-Object System.Management.Automation.PSCredential(
            $env:SMTP_USER,
            (ConvertTo-SecureString $env:SMTP_PASSWORD -AsPlainText -Force)
        )
    }

    try {
        Send-MailMessage @EmailParams
        Write-Log "Email notification sent"
    } catch {
        Write-Log "Failed to send email: $_"
    }
}

exit $DeltaSyncExitCode
