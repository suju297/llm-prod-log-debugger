#!/bin/bash
# Demo script for Multi-LLM Production Log Debugger

echo "🚀 Multi-LLM Production Log Debugger Demo"
echo "========================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Please copy .env.example to .env and add your Gemini API key"
    exit 1
fi

# Create output directory
mkdir -p out

# Check if Poetry is available
if command -v poetry &> /dev/null; then
    echo "📊 Analyzing sample production incident (using Poetry)..."
    echo ""
    poetry run python -m src.orchestrator.main demo
else
    echo "📊 Analyzing sample production incident (using pip)..."
    echo ""
    python -m src.orchestrator.main demo
fi

echo ""
echo "✅ Demo complete! Check the 'out' directory for:"
echo "  - report_*.md (Incident report)"
echo "  - conversation_*.json (Full analysis history)"
echo "  - metrics_*.json (Token usage and performance)"
