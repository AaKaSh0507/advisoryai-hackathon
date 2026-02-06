#!/bin/bash
set -e

COMMAND=${1:-api}
PORT=${PORT:-8000}

case "$COMMAND" in
    api)
        echo "Running migrations..."
        cd backend && alembic upgrade head && cd ..
        echo "Starting API on port $PORT..."
        exec uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
        ;;
    worker)
        echo "Starting Worker..."
        exec python -m backend.app.worker.main
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo "Usage: $0 {api|worker}"
        exit 1
        ;;
esac
