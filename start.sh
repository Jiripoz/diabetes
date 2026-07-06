#!/usr/bin/env bash
# Single entrypoint for both Railway services. SERVICE_ROLE selects which runs.
set -euo pipefail

if [ "${SERVICE_ROLE:-web}" = "bot" ]; then
  exec python -m app.bot.main
else
  python -m app.migrate
  exec uvicorn app.web.main:app --host 0.0.0.0 --port "${PORT:-8000}"
fi
