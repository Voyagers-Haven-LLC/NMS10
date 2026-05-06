#!/usr/bin/env bash
# Local dev runner. Activates the bot's venv, loads .env if present, runs the bot.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r requirements.txt
fi

# Load .env if present
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# Run from the repo root so `bot.main` resolves cleanly
cd "$(dirname "$DIR")"
exec "$DIR/.venv/bin/python" -m bot.main "$@"
