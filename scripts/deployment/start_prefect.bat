@echo off
REM ============================================================================
REM Start Prefect Server + Worker for Market Scraper Delta Sync
REM ============================================================================
REM This script starts both the Prefect server and worker automatically.
REM Place this file in your Startup folder for automatic execution on login.
REM ============================================================================

echo.
echo ===================================================
echo   Market Scraper - Prefect Orchestration Startup
echo ===================================================
echo.

REM Navigate to project root
cd /d "%~dp0.."
echo Project Root: %CD%
echo.

REM Configure Prefect API URL
echo [1/3] Configuring Prefect API URL...
prefect config set PREFECT_API_URL="http://127.0.0.1:4200/api"
echo.

REM Start Prefect server in a new window
echo [2/3] Starting Prefect server...
start "Prefect Server" /MIN cmd /c "prefect server start"
echo   Server starting in background window...
echo   Dashboard: http://127.0.0.1:4200
echo.

REM Wait for server to be ready
echo [3/3] Waiting for server to start (15 seconds)...
timeout /t 15 /nobreak >nul
echo.

REM Start Prefect worker in a new window
echo Starting Prefect worker...
start "Prefect Worker" /MIN cmd /c "prefect worker start --pool market-scraper-pool"
echo   Worker started in background window
echo.

echo ===================================================
echo   Prefect Orchestration Started Successfully!
echo ===================================================
echo.
echo Dashboard: http://127.0.0.1:4200
echo Schedule: Daily at 9:00 AM
echo.
echo Both server and worker are running in minimized windows.
echo Close those windows to stop the orchestration.
echo.
pause