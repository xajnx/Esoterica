#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
FRONTEND_URL="http://localhost:${FRONTEND_PORT}"

if [[ ! -x "$BACKEND_DIR/.venv/bin/python" ]]; then
  echo "Missing backend virtualenv at $BACKEND_DIR/.venv"
  echo "Create it first:"
  echo "  cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [[ ! -f "$FRONTEND_DIR/package.json" ]]; then
  echo "Frontend package.json not found in $FRONTEND_DIR"
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && npm install)
fi

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting backend on :$BACKEND_PORT ..."
(
  cd "$BACKEND_DIR"
  "$BACKEND_DIR/.venv/bin/python" -m uvicorn app:app --reload --port "$BACKEND_PORT" --app-dir "$BACKEND_DIR"
) &
BACKEND_PID=$!

if command -v xdg-open >/dev/null 2>&1; then
  # Open once; Vite may take a few seconds to become available.
  (sleep 2 && xdg-open "$FRONTEND_URL" >/dev/null 2>&1 || true) &
fi

echo "Starting frontend on :$FRONTEND_PORT ..."
cd "$FRONTEND_DIR"
npm run dev -- --host --port "$FRONTEND_PORT"
