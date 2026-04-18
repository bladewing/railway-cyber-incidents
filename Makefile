.PHONY: install validate build test lint clean

install:
	python -m pip install -e ".[dev]"

validate:
	python scripts/validate.py

build:
	python scripts/build_release.py

test:
	pytest -v

lint:
	ruff check .

clean:
	rm -rf dist/ .pytest_cache/ .ruff_cache/ **/__pycache__
