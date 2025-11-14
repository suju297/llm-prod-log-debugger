#!/bin/bash
# Local development run script

# Create output directory if needed
mkdir -p out

# Check if Poetry is available and use it, otherwise fallback to regular Python
if command -v poetry &> /dev/null; then
    echo "Using Poetry environment..."
    poetry run python -m src.orchestrator.main "$@"
else
    echo "Poetry not found, using system Python..."
    
    # Activate virtual environment if it exists
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    
    # Set Python path
    export PYTHONPATH="${PYTHONPATH}:$(pwd)"
    
    # Run with custom arguments
    python -m src.orchestrator.main "$@"
fi
