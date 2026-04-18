.PHONY: install validate build test lint clean

install:
	uv sync

validate:
	uv run python scripts/validate.py

build:
	uv run python scripts/build_release.py

test:
	uv run pytest -v

lint:
	uv run ruff check .

clean:
	rm -rf dist/ .pytest_cache/ .ruff_cache/ **/__pycache__
