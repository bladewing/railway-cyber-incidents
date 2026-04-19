.PHONY: install validate build test lint clean discover discover-fetch discover-stub

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

discover:          ## Full discovery: fetch candidates + write stubs
	uv run python -m scripts.fetch_candidates
	uv run python -m scripts.stub_candidates

discover-fetch:    ## Stage 1 only — refresh dist/candidates.json
	uv run python -m scripts.fetch_candidates

discover-stub:     ## Stage 2 only — re-run LLM on existing candidates.json
	uv run python -m scripts.stub_candidates
