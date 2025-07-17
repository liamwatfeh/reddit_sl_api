.PHONY: help install test lint format type-check dev clean build run-prod

# Default target
help:
	@echo "Available commands:"
	@echo "  install     - Install dependencies"
	@echo "  test        - Run pytest"
	@echo "  lint        - Run flake8 linting"
	@echo "  format      - Run black code formatting"
	@echo "  type-check  - Run mypy type checking"
	@echo "  dev         - Run uvicorn development server with reload"
	@echo "  run-prod    - Run uvicorn production server"
	@echo "  clean       - Clean cache and build files"
	@echo "  build       - Run all checks (lint, type-check, test)"
	@echo "  setup       - Complete development setup"

# Install dependencies
install:
	pip install -r requirements.txt

# Run tests
test:
	cd reddit-build && python3 -m pytest tests/ -v

# Run linting
lint:
	cd reddit-build && flake8 app/ tests/

# Format code
format:
	cd reddit-build && black app/ tests/

# Type checking
type-check:
	cd reddit-build && mypy app/

# Run development server
dev:
	cd reddit-build && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run production server
run-prod:
	cd reddit-build && uvicorn app.main:app --host 0.0.0.0 --port 8000

# Clean cache and build files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +

# Run all checks
build: format lint type-check test
	@echo "All checks passed!"

# Complete development setup
setup: install
	@echo "Development environment setup complete!"
	@echo "Run 'make dev' to start the development server"
	@echo "Run 'make test' to run tests"
	@echo "Run 'make help' to see all available commands" 