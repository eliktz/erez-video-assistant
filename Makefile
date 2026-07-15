.PHONY: setup test lint fix run digest-preview

setup:
	uv sync
	@echo "Ready. Copy .env.example to .env and fill it in."

test:
	uv run pytest -q

lint:
	uv run ruff check .

fix:
	uv run ruff check --fix .
	uv run ruff format .

run:
	uv run --env-file .env python -m app.main

digest-preview:
	uv run python -m app.digest.page --from-fixtures
