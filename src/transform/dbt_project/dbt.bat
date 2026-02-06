@echo off
REM =========================================================================
REM DBT Wrapper Script for Windows
REM Automatically sets PYTHONUTF8=1 to handle encoding issues
REM =========================================================================

REM Set UTF-8 encoding for Python
set PYTHONUTF8=1

REM Forward all arguments to dbt
dbt %*

REM Exit with the same code as dbt
exit /b %ERRORLEVEL%
