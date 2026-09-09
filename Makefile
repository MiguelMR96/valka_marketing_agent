.PHONY: install test smoke demo

install:
	uv sync --extra dev

test:
	uv run python -m pytest tests/ -v

smoke:
	uv run python scripts/smoke.py

# `make` isn't guaranteed to be installed — scripts/demo.sh is the primary
# documented cold-start command and doesn't depend on make being present.
demo:
	./scripts/demo.sh
