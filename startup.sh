#!/bin/bash
set -e

echo "Installing Python dependencies..."
pip install -q -r requirements.txt

if [ ! -d "frontend/dist" ]; then
    echo "Building frontend..."
    cd frontend && npm ci && npm run build && cd ..
fi

exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
