#!/usr/bin/env bash
# ASSISTRAN — one-command run.
# Installs deps, builds the frontend + backend, then starts a single server
# that serves BOTH the API and the web UI on one port.
#
# Usage:
#   ./run.sh
#   PORT=3000 OLLAMA_URL=http://my-ollama:11434 ./run.sh
set -euo pipefail
cd "$(dirname "$0")"

# Default to a local Ollama (same machine). Override OLLAMA_URL for a remote one,
# e.g. OLLAMA_URL=http://46.152.253.223:11434 ./run.sh
export OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
export MODEL_NAME="${MODEL_NAME:-qwen2.5-coder:32b}"
export PORT="${PORT:-8080}"

echo "==> Installing dependencies"
npm install

echo "==> Building frontend + backend"
npm run build

echo ""
echo "============================================================"
echo "  ASSISTRAN is starting on a single port."
echo "  OLLAMA_URL = $OLLAMA_URL"
echo "  MODEL_NAME = $MODEL_NAME"
echo ""
echo "  >>> Open this link in Chrome or Edge:"
echo "  >>> http://localhost:$PORT"
echo "============================================================"
echo ""

npm run start
