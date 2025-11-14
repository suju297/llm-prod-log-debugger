.PHONY: help install test lint format clean demo

help:
	@echo "Available commands:"
	@echo "  install    Install dependencies with Poetry"
	@echo "  test       Run tests"
	@echo "  lint       Run linters"
	@echo "  format     Format code"
	@echo "  clean      Clean up generated files"
	@echo "  demo       Run demo analysis"

install:
	poetry install

test:
	poetry run pytest -v

lint:
	poetry run ruff check src tests
	poetry run mypy src

format:
	poetry run black src tests
	poetry run ruff check --fix src tests

clean:
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf out/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

demo:
	poetry run log-debugger demo

pre-commit:
	poetry run pre-commit run --all-files
