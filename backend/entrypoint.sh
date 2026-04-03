#!/bin/bash
set -e

echo "Starting SK Survey Backend..."

exec uvicorn src.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --reload
