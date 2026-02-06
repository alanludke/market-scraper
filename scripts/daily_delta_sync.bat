@echo off
REM ============================================================================
REM Daily Delta Sync - OpenFoodFacts Incremental Updates
REM ============================================================================
REM
REM This script:
REM 1. Runs OpenFoodFacts delta sync to update EAN data
REM 2. Updates DBT models (dim_ean)
REM 3. Logs execution results
REM
REM Schedule: Daily at 2:00 AM (via Task Scheduler)
REM ============================================================================

echo [%date% %time%] Starting daily delta sync...

REM Change to project directory
cd /d "%~dp0.."

REM Activate virtual environment (if using one)
REM call venv\Scripts\activate.bat

REM Run delta sync
echo [%date% %time%] Running delta-sync...
python cli_enrich.py delta-sync > logs\delta_sync_%date:~-4,4%%date:~-10,2%%date:~-7,2%.log 2>&1

REM Check if delta sync succeeded
if %ERRORLEVEL% EQU 0 (
    echo [%date% %time%] Delta sync completed successfully

    REM Update DBT models
    echo [%date% %time%] Updating DBT models...
    cd src\transform\dbt_project
    dbt run --select stg_openfoodfacts__products dim_ean >> ..\..\..\logs\delta_sync_%date:~-4,4%%date:~-10,2%%date:~-7,2%.log 2>&1

    if %ERRORLEVEL% EQU 0 (
        echo [%date% %time%] DBT update completed successfully
    ) else (
        echo [%date% %time%] ERROR: DBT update failed with code %ERRORLEVEL%
    )

    cd ..\..\..
) else (
    echo [%date% %time%] ERROR: Delta sync failed with code %ERRORLEVEL%
)

echo [%date% %time%] Daily delta sync finished

REM Optional: Send notification (requires curl or PowerShell)
REM curl -X POST "https://your-notification-service.com/notify" -d "status=completed"

exit /b %ERRORLEVEL%
