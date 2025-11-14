# Local development run script (PowerShell version)
param(
    [Parameter(ValueFromRemainingArguments)]
    [string[]]$Arguments
)

# Create output directory if needed
if (-not (Test-Path "out")) {
    New-Item -ItemType Directory -Path "out" | Out-Null
}

# Check if Poetry is available and use it, otherwise fallback to regular Python
if (Get-Command poetry -ErrorAction SilentlyContinue) {
    Write-Host "Using Poetry environment..." -ForegroundColor Green
    $cmd = "poetry run python -m src.orchestrator.main"
    if ($Arguments) {
        $cmd += " " + ($Arguments -join " ")
    }
    Invoke-Expression $cmd
} else {
    Write-Host "Poetry not found, using system Python..." -ForegroundColor Yellow
    
    # Set Python path
    $env:PYTHONPATH = "$env:PYTHONPATH;$(Get-Location)"
    
    # Run with custom arguments
    $cmd = "python -m src.orchestrator.main"
    if ($Arguments) {
        $cmd += " " + ($Arguments -join " ")
    }
    Invoke-Expression $cmd
}
