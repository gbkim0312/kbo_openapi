.PHONY: install lint format type-check test check migrate
install:
	uv sync --all-groups
lint:
	uv run ruff check .
format:
	uv run ruff format .
type-check:
	uv run mypy app
test:
	uv run pytest
check: lint type-check test
migrate:
	uv run alembic upgrade head
