#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAC_DIR="$SCRIPT_DIR/mac"
SRC_DIR="$MAC_DIR/src"
UTILS_DIR="$SCRIPT_DIR/utils"
FRONTEND_DIR="$MAC_DIR/frontend"
VENV="$MAC_DIR/.ilgc"
PYTHON="$VENV/bin/python3"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo "[ILGC] $1"; }
ok()   { echo "[ILGC-OK] $1"; }
warn() { echo "[ILGC-WARN] $1"; }
err()  { echo "[ILGC-ERROR] $1"; }

declare -a PIDS

cleanup() {
  echo ""
  log "Shutting down all services..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null
  done
  sleep 2
  for pid in "${PIDS[@]}"; do
    kill -9 "$pid" 2>/dev/null
  done
  pkill -f "aw-qt"      2>/dev/null || true
  pkill -f "aw-server"  2>/dev/null || true
  pkill -f "aw-watcher" 2>/dev/null || true
  sleep 1
  pkill -9 -f "aw-qt"      2>/dev/null || true
  pkill -9 -f "aw-server"  2>/dev/null || true
  pkill -9 -f "aw-watcher" 2>/dev/null || true
  ok "All services stopped."
  exit 0
}

trap cleanup SIGINT SIGTERM SIGHUP EXIT

echo ""
echo "ILGC Workplace and Distraction Monitor - Mac"
echo ""

# STEP 1 - Homebrew
log "Checking Homebrew..."
if ! command -v brew &>/dev/null; then
  log "Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
if [ -f "/opt/homebrew/bin/brew" ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -f "/usr/local/bin/brew" ]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi
ok "Homebrew ready"

# STEP 2 - Python 3.12
log "Checking Python 3.12..."
if ! command -v python3.12 &>/dev/null; then
  log "Installing Python 3.12..."
  brew install python@3.12
  export PATH="$(brew --prefix python@3.12)/bin:$PATH"
fi
PYTHON312="$(command -v python3.12)"
ok "Python 3.12 ready: $(python3.12 --version)"

# STEP 3 - Node.js
log "Checking Node.js..."
if ! command -v node &>/dev/null; then
  log "Installing Node.js..."
  brew install node
fi
ok "Node.js ready: $(node --version)"

# STEP 4 - ActivityWatch
AW_SCRIPT="$UTILS_DIR/mac.sh"
if [ ! -f "$AW_SCRIPT" ]; then
  err "utils/mac.sh not found at $AW_SCRIPT"
  exit 1
fi
log "Launching ActivityWatch..."
chmod +x "$AW_SCRIPT"
bash "$AW_SCRIPT" &
AW_PID=$!
PIDS+=("$AW_PID")
ok "ActivityWatch launched (PID $AW_PID)"
sleep 5

# STEP 5 - Check mac/ directory
if [ ! -d "$MAC_DIR" ]; then
  err "Could not find 'mac/' directory at: $MAC_DIR"
  exit 1
fi

# STEP 6 - Virtual environment
log "Checking virtual environment..."
if [ ! -f "$PYTHON" ]; then
  log "Creating .ilgc venv..."
  "$PYTHON312" -m venv "$VENV"
fi
ok "Virtual environment ready"

# STEP 7 - Python dependencies
REQUIREMENTS="$MAC_DIR/requirements.txt"
if [ ! -f "$REQUIREMENTS" ]; then
  err "requirements.txt not found at $REQUIREMENTS"
  exit 1
fi

log "Checking Python dependencies..."
if ! "$PYTHON" -c "import flask" 2>/dev/null; then
  log "Installing Python dependencies..."
  "$PYTHON" -m pip install --upgrade pip --quiet
  "$PYTHON" -m pip install -r "$REQUIREMENTS" --quiet
fi
ok "Python dependencies ready"

# Copy pylsl lib files if present
PYLSL_LIB="$MAC_DIR/lib/pylsl"
PYLSL_DEST_DYNAMIC=$("$PYTHON" -c "import pylsl, os; print(os.path.join(os.path.dirname(pylsl.__file__), 'lib'))" 2>/dev/null || true)
if [ -d "$PYLSL_LIB" ] && [ -n "$PYLSL_DEST_DYNAMIC" ] && [ -d "$PYLSL_DEST_DYNAMIC" ]; then
  cp -r "$PYLSL_LIB/"* "$PYLSL_DEST_DYNAMIC/" 2>/dev/null || true
fi

# STEP 8 - Frontend dependencies
log "Checking frontend dependencies..."
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  log "Installing frontend dependencies..."
  cd "$FRONTEND_DIR" && npm install --silent
  cd "$SCRIPT_DIR"
fi
ok "Frontend dependencies ready"

# STEP 9 - Start Python backend services
log "Starting api_server.py..."
cd "$MAC_DIR"
"$PYTHON" api_server.py >> "$MAC_DIR/api_server.log" 2>&1 &
PID=$!; PIDS+=("$PID")
ok "api_server.py started (PID $PID)"
sleep 2

log "Starting watch.py..."
cd "$SRC_DIR"
"$PYTHON" watch.py >> "$MAC_DIR/watch.log" 2>&1 &
PID=$!; PIDS+=("$PID")
ok "watch.py started (PID $PID)"
sleep 1

log "Starting client.py..."
cd "$SRC_DIR"
"$PYTHON" client.py >> "$MAC_DIR/client.log" 2>&1 &
PID=$!; PIDS+=("$PID")
ok "client.py started (PID $PID)"
sleep 1

log "Starting collate_data.py..."
cd "$SRC_DIR"
"$PYTHON" collate_data.py >> "$MAC_DIR/collate_data.log" 2>&1 &
PID=$!; PIDS+=("$PID")
ok "collate_data.py started (PID $PID)"
sleep 1

if [ -f "$UTILS_DIR/run_activity.py" ]; then
  log "Starting run_activity.py..."
  cd "$SRC_DIR"
  "$PYTHON" "$UTILS_DIR/run_activity.py" >> "$MAC_DIR/run_activity.log" 2>&1 &
  PID=$!; PIDS+=("$PID")
  ok "run_activity.py started (PID $PID)"
  sleep 1
fi

# STEP 10 - Start frontend
log "Starting frontend (Vite)..."
cd "$FRONTEND_DIR"
npm run dev >> "$MAC_DIR/frontend.log" 2>&1 &
PID=$!; PIDS+=("$PID")
ok "Frontend started (PID $PID)"

# Wait for API to be ready
log "Waiting for API server to be ready..."
MAX_WAIT=60
COUNT=0
while [ $COUNT -lt $MAX_WAIT ]; do
  if curl -s http://localhost:5002/api/health > /dev/null 2>&1; then
    ok "API server is ready"
    break
  fi
  sleep 1
  COUNT=$((COUNT + 1))
done

if [ $COUNT -ge $MAX_WAIT ]; then
  err "API server did not start within ${MAX_WAIT} seconds"
fi

# This exact string is what electron/main.js listens for
echo "All services running"

echo ""
echo "API server    -> http://localhost:5002"
echo "Frontend      -> http://localhost:8080"
echo "ActivityWatch -> http://localhost:5600"
echo ""
echo "Press Ctrl+C to stop everything."
echo ""

wait