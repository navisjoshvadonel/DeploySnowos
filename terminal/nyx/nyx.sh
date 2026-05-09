#!/bin/bash

INPUT="$*"
CONFIG_FILE="${SNOWOS_CONFIG_FILE:-$HOME/.snowos/config.json}"
HOST="${SNOWOS_API_HOST:-127.0.0.1}"
PORT="${SNOWOS_API_PORT:-}"
API_KEY="${SNOWOS_API_KEY:-}"

if [ -z "$INPUT" ]; then
  echo "SnowOS Nyx Terminal Ready"
  echo "Usage: nyx \"command\""
  exit 0
fi

if [ -z "$PORT" ] && [ -f "$CONFIG_FILE" ]; then
  PORT=$(sed -n 's/.*"api_port"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$CONFIG_FILE" | head -n 1)
fi

if [ -z "$API_KEY" ] && [ -f "$CONFIG_FILE" ]; then
  API_KEY=$(sed -n 's/.*"api_key"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$CONFIG_FILE" | head -n 1)
fi

PORT="${PORT:-8080}"

if [ -z "$API_KEY" ]; then
  echo "SnowOS API key not found. Set SNOWOS_API_KEY or create $CONFIG_FILE first."
  exit 1
fi

curl -s "http://$HOST:$PORT/run" \
  -H "Content-Type: application/json" \
  -H "X-Nyx-Key: $API_KEY" \
  -d "{\"command\":\"$INPUT\"}" | jq 2>/dev/null || cat
