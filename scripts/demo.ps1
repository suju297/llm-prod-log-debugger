# Demo script for Multi-LLM Production Log Debugger (PowerShell version)

Write-Host "🚀 Multi-LLM Production Log Debugger Demo" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "❌ Error: .env file not found" -ForegroundColor Red
    Write-Host "Please copy .env.example to .env and add your Gemini API key" -ForegroundColor Yellow
    exit 1
}

# Create output directory
if (-not (Test-Path "out")) {
    New-Item -ItemType Directory -Path "out" | Out-Null
}

# Check if Poetry is available
if (Get-Command poetry -ErrorAction SilentlyContinue) {
    Write-Host "📊 Analyzing sample production incident (using Poetry)..." -ForegroundColor Cyan
    Write-Host ""
    poetry run python -m src.orchestrator.main demo
} else {
    Write-Host "📊 Analyzing sample production incident (using pip)..." -ForegroundColor Cyan
    Write-Host ""
    python -m src.orchestrator.main demo
}

Write-Host ""
Write-Host "✅ Demo complete! Check the 'out' directory for:" -ForegroundColor Green
Write-Host "  - report_*.md (Incident report)" -ForegroundColor White
Write-Host "  - conversation_*.json (Full analysis history)" -ForegroundColor White
Write-Host "  - metrics_*.json (Token usage and performance)" -ForegroundColor White
