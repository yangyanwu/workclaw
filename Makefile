.PHONY: install dev cli test lint clean help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install WorkClaw with all dependencies
	pip install -e ".[dev]"

dev: ## Run the GUI dev server
	uvicorn workclaw.gui.server:app --reload --host 0.0.0.0 --port 8000

cli: ## Run the CLI in interactive chat mode
	workclaw chat

test: ## Run all tests
	pytest -v

lint: ## Run linting (ruff + mypy)
	ruff check src/ tests/
	ruff format --check src/ tests/

format: ## Auto-format code
	ruff check --fix src/ tests/
	ruff format src/ tests/

clean: ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
