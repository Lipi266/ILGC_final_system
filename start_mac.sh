#!/bin/bash

# ─────────────────────────────────────────────────────────────
# ILGC Mac Launcher
# Installs Homebrew, Python 3.12, Node.js, ActivityWatch,
# sets up venv, then starts all services in one script.
# Press Ctrl+C to stop everything cleanly.
# ─────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAC_DIR="$SCRIPT_DIR/mac"
SRC_DIR="$MAC_DIR/src"
UTILS_DIR="$SCRIPT_DIR/utils"
FRONTEND_DIR="$MAC_DIR/frontend"
VENV="$MAC_DIR/.ilgc"
PYTHON="$VENV/bin/python3"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${CYAN}[ILGC]${RESET} $1"; }
ok()   { echo -e "${GREEN}[ILGC]${RESET} $1"; }
warn() { echo -e "${YELLOW}[ILGC]${RESET} $1"; }
err()  { echo -e "${RED}[ILGC]${RESET} $1"; }

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
  ok "All services stopped. Goodbye!"
  exit 0
}

trap cleanup SIGINT SIGTERM SIGHUP EXIT

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}   ILGC Workplace & Distraction Monitor — Mac      ${RESET}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""

# ─────────────────────────────────────────────────────────────
# STEP 1 — Homebrew
# ─────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
  log "Homebrew not found. Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [ -f "/opt/homebrew/bin/brew" ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [ -f "/usr/local/bin/brew" ]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
  ok "Homebrew installed."
else
  ok "Homebrew found."
fi

if [ -f "/opt/homebrew/bin/brew" ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -f "/usr/local/bin/brew" ]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

# ─────────────────────────────────────────────────────────────
# STEP 2 — Python 3.12
# ─────────────────────────────────────────────────────────────
if ! command -v python3.12 &>/dev/null; then
  log "Python 3.12 not found. Installing via Homebrew..."
  brew install python@3.12
  export PATH="$(brew --prefix python@3.12)/bin:$PATH"
  ok "Python 3.12 installed."
else
  ok "Python 3.12 found: $(python3.12 --version)"
fi
PYTHON312="$(command -v python3.12)"

# ─────────────────────────────────────────────────────────────
# STEP 3 — Node.js
# ─────────────────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
  log "Node.js not found. Installing via Homebrew..."
  brew install node
  ok "Node.js installed: $(node --version)"
else
  ok "Node.js found: $(node --version)"
fi

if ! command -v npm &>/dev/null; then
  err "npm still not found after Node.js install. Please restart the script."
  exit 1
fi

# ─────────────────────────────────────────────────────────────
# STEP 4 — ActivityWatch (via utils/mac.sh)
# ─────────────────────────────────────────────────────────────
AW_SCRIPT="$UTILS_DIR/mac.sh"

if [ ! -f "$AW_SCRIPT" ]; then
  err "utils/mac.sh not found at $AW_SCRIPT"
  exit 1
fi

log "Running utils/mac.sh for ActivityWatch setup and launch..."
chmod +x "$AW_SCRIPT"
bash "$AW_SCRIPT" &
AW_PID=$!
PIDS+=("$AW_PID")
ok "ActivityWatch launched via mac.sh (PID $AW_PID)"
sleep 5  # give AW time to fully start before proceeding

# ─────────────────────────────────────────────────────────────
# STEP 5 — Check mac/ directory
# ─────────────────────────────────────────────────────────────
if [ ! -d "$MAC_DIR" ]; then
  err "Could not find 'mac/' directory at: $MAC_DIR"
  err "Make sure you run this script from the project root."
  exit 1
fi

# ─────────────────────────────────────────────────────────────
# STEP 6 — Virtual environment (mac/.ilgc)
# ─────────────────────────────────────────────────────────────
if [ ! -f "$PYTHON" ]; then
  log "Creating .ilgc venv with Python 3.12..."
  "$PYTHON312" -m venv "$VENV"
  ok "Virtual environment created."
else
  ok "Virtual environment found."
fi

# ─────────────────────────────────────────────────────────────
# STEP 7 — Python dependencies (mac/requirements.txt)
# ─────────────────────────────────────────────────────────────
REQUIREMENTS="$MAC_DIR/requirements.txt"
if [ ! -f "$REQUIREMENTS" ]; then
  err "requirements.txt not found at $REQUIREMENTS"
  exit 1
fi

if ! "$PYTHON" -c "import flask" 2>/dev/null; then
  log "Installing Python dependencies..."
  "$PYTHON" -m pip install --upgrade pip --quiet
  "$PYTHON" -m pip install -r "$REQUIREMENTS" --quiet
  ok "Python dependencies installed."
else
  ok "Python dependencies already installed."
fi

# Copy pylsl lib files if present
PYLSL_LIB="$MAC_DIR/lib/pylsl"
PYLSL_DEST_DYNAMIC=$("$PYTHON" -c "import pylsl, os; print(os.path.join(os.path.dirname(pylsl.__file__), 'lib'))" 2>/dev/null || true)
if [ -d "$PYLSL_LIB" ] && [ -n "$PYLSL_DEST_DYNAMIC" ] && [ -d "$PYLSL_DEST_DYNAMIC" ]; then
  log "Copying pylsl lib files..."
  cp -r "$PYLSL_LIB/"* "$PYLSL_DEST_DYNAMIC/" 2>/dev/null || true
  ok "pylsl lib files copied."
fi

# ─────────────────────────────────────────────────────────────
# STEP 8 — Frontend dependencies
# ─────────────────────────────────────────────────────────────
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  log "Installing frontend dependencies (first run)..."
  cd "$FRONTEND_DIR" && npm install --silent
  ok "Frontend dependencies installed."
  cd "$SCRIPT_DIR"
fi

# ─────────────────────────────────────────────────────────────
# STEP 9 — Start Python backend services
# ─────────────────────────────────────────────────────────────

# api_server.py — mac/
log "Starting api_server.py..."
cd "$MAC_DIR"
"$PYTHON" api_server.py &
PID=$!; PIDS+=("$PID")
ok "api_server.py started (PID $PID)"
sleep 1

# watch.py — mac/src/
log "Starting watch.py..."
cd "$SRC_DIR"
"$PYTHON" watch.py &
PID=$!; PIDS+=("$PID")
ok "watch.py started (PID $PID)"
sleep 1

# client.py — mac/src/
log "Starting client.py..."
cd "$SRC_DIR"
"$PYTHON" client.py &
PID=$!; PIDS+=("$PID")
ok "client.py started (PID $PID)"
sleep 1

# collate_data.py — mac/src/
log "Starting collate_data.py..."
cd "$SRC_DIR"
"$PYTHON" collate_data.py &
PID=$!; PIDS+=("$PID")
ok "collate_data.py started (PID $PID)"
sleep 1

# run_activity.py — run from mac/src/ so activity.json lands at
# mac/src/activityTracker/activity.json (where collate_data.py reads it)
if [ -f "$UTILS_DIR/run_activity.py" ]; then
  log "Starting run_activity.py..."
  cd "$SRC_DIR"
  "$PYTHON" "$UTILS_DIR/run_activity.py" &
  PID=$!; PIDS+=("$PID")
  ok "run_activity.py started (PID $PID)"
  sleep 1
else
  warn "run_activity.py not found at $UTILS_DIR — skipping."
fi

# ─────────────────────────────────────────────────────────────
# STEP 11 — Start frontend
# ─────────────────────────────────────────────────────────────
log "Starting frontend (Vite)..."
cd "$FRONTEND_DIR"
npm run dev &
PID=$!; PIDS+=("$PID")
ok "Frontend started (PID $PID)"

# ─────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
ok "All services running!"
echo ""
echo -e "  ${CYAN}API server${RESET}    → http://localhost:5002"
echo -e "  ${CYAN}Frontend${RESET}      → http://localhost:8080"
echo -e "  ${CYAN}ActivityWatch${RESET} → http://localhost:5600"
echo ""
echo -e "  Press ${BOLD}Ctrl+C${RESET} to stop everything."
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""

wait