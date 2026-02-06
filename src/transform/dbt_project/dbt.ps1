# =========================================================================
# DBT Wrapper Script for Windows PowerShell
# Automatically sets PYTHONUTF8=1 to handle encoding issues
# =========================================================================

# Set UTF-8 encoding for Python
$env:PYTHONUTF8 = "1"

# Forward all arguments to dbt
& dbt @args

# Exit with the same code as dbt
exit $LASTEXITCODE
