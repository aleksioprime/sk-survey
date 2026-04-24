#!/bin/bash
set -e

echo "Starting SK Survey Backend..."

if [ "${BACKEND_RELOAD:-0}" = "1" ]; then
  exec uvicorn src.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --reload
fi

exec uvicorn src.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
