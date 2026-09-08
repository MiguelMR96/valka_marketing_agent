#!/usr/bin/env bash
# One-command cold-start: install deps, run unit tests, run the smoke script.
# `make` is not guaranteed to be installed (it isn't on the machine this was
# built on) — this script is the primary documented entry point; the
# Makefile wraps it for convenience where `make` exists.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found — install it with: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

uv sync --extra dev
uv run pytest tests/ -v
uv run python scripts/smoke.py
