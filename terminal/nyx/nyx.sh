#!/bin/bash

INPUT="$*"

if [ -z "$INPUT" ]; then
  echo "❄ Nyx Terminal Ready"
  echo "Usage: nyx \"command\""
  exit 0
fi

# Route to Nyx Core API
curl -s http://localhost:4040/run \
  -H "Content-Type: application/json" \
  -H "X-Nyx-Key: 03bd675c" \
  -d "{\"command\":\"$INPUT\"}" | jq 2>/dev/null || cat
