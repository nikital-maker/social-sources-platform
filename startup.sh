#!/bin/bash
set -e

if [ ! -d "frontend/dist" ]; then
    echo "Building frontend..."
    cd frontend && npm ci && npm run build && cd ..
fi

exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
