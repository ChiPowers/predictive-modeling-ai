.PHONY: install install-dev lint fmt typecheck test test-cov clean serve pipeline

PYTHON  ?= python3
PIP     ?= pip
SOURCE  ?= csv:data/raw/sample.csv
MODEL   ?= prophet

# ── Setup ────────────────────────────────────────────────────────────────────
install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"
	pre-commit install

# ── Code quality ─────────────────────────────────────────────────────────────
lint:
	ruff check .

fmt:
	ruff format .
	ruff check --fix .

typecheck:
	mypy .

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	pytest

test-cov:
	pytest --cov=. --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

# ── Run ───────────────────────────────────────────────────────────────────────
ingest:
	$(PYTHON) -m main ingest --source $(SOURCE)

features:
	$(PYTHON) -m main features --source $(SOURCE)

train:
	$(PYTHON) -m main train --model $(MODEL)

serve:
	$(PYTHON) -m main serve

pipeline:
	$(PYTHON) -m main pipeline --source $(SOURCE) --model $(MODEL)

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage dist build
