#!/bin/bash

# SnowOS Nyx Bootstrap
# Launches the Autonomous Kernel and Intelligence Layers

PROJECT_ROOT="/home/develop/snowos"
LOG_DIR="$PROJECT_ROOT/logs"
UI_STATE="$PROJECT_ROOT/nyx/ui_state.json"

mkdir -p "$LOG_DIR"

echo "❄️  Initializing SnowOS Sentient Layers..."

# 1. Ensure UI State exists
if [ ! -f "$UI_STATE" ]; then
    echo "Creating initial UI state..."
    cat <<EOF > "$UI_STATE"
{
  "focus_level": "idle",
  "system_stress": 0.0,
  "user_intent": "idle",
  "last_interaction": $(date +%s),
  "performance_mode": "calm",
  "ai_active": false
}
EOF
fi

# 2. Launch Nyx Engine in background
echo "🚀 Launching Nyx Engine..."
cd "$PROJECT_ROOT"
nohup python3 nyx/nyx.py > "$LOG_DIR/nyx.log" 2>&1 &

PID=$!
echo "$PID" > "$LOG_DIR/nyx.pid"

echo "✅ SnowOS Nyx Engine started (PID: $PID)"
echo "Logs available at: $LOG_DIR/nyx.log"
