#!/bin/bash
# dev.sh — Start both backend and frontend, kill any existing processes on their ports

set -e

echo "🧹 Killing existing processes on ports 8000 and 5173..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
sleep 0.5

echo "🚀 Starting backend (port 8000)..."
cd "$(dirname "$0")"
source .venv/bin/activate
uvicorn src.api:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "🎨 Starting frontend (port 5173)..."
cd frontend
bun run dev &
FRONTEND_PID=$!

echo ""
echo "  Backend:  http://localhost:8000/api/health"
echo "  Frontend: http://localhost:5173"
echo ""
echo "  Press Ctrl+C to stop both"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
