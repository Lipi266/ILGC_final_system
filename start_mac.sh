#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAC_DIR="$SCRIPT_DIR/mac"
SRC_DIR="$MAC_DIR/src"
UTILS_DIR="$SCRIPT_DIR/utils"
FRONTEND_DIR="$MAC_DIR/frontend"
APP_NAME="ILGC Research"
APP_SUPPORT_DIR="$HOME/Library/Application Support/$APP_NAME"
APP_LOG_DIR="$HOME/Library/Logs/$APP_NAME"
APP_DATA_DIR="$APP_SUPPORT_DIR/data"
APP_DATA_LOG_DIR="$APP_DATA_DIR/logs"
SERVICE_LOG_DIR="$APP_DATA_LOG_DIR/services"
VENV="$APP_SUPPORT_DIR/venvs/mac"
PYTHON="$VENV/bin/python3"
PIP_LOG="$APP_DATA_LOG_DIR/pip_install.log"
AW_BOOTSTRAP_LOG="$APP_DATA_LOG_DIR/activitywatch_bootstrap.log"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo "[ILGC] $1"; }
ok()   { echo "[ILGC-OK] $1"; }
warn() { echo "[ILGC-WARN] $1"; }
err()  { echo "[ILGC-ERROR] $1"; }

ensure_linked_dir() {
  local link_path="$1"
  local target_path="$2"
  local backup_path

  mkdir -p "$target_path"
  mkdir -p "$(dirname "$link_path")"

  if [ -L "$link_path" ]; then
    local current_target
    current_target="$(readlink "$link_path")"
    if [ "$current_target" != "$target_path" ]; then
      rm -f "$link_path"
      ln -s "$target_path" "$link_path"
    fi
    return
  fi

  if [ -d "$link_path" ]; then
    if [ -n "$(ls -A "$link_path" 2>/dev/null)" ]; then
      cp -a "$link_path"/. "$target_path"/ 2>/dev/null || true
    fi
    backup_path="${link_path}.legacy_$(date +%Y%m%d_%H%M%S)"
    mv "$link_path" "$backup_path"
    ln -s "$target_path" "$link_path"
    return
  fi

  if [ -e "$link_path" ]; then
    backup_path="${link_path}.legacy_$(date +%Y%m%d_%H%M%S)"
    mv "$link_path" "$backup_path"
  fi

  ln -s "$target_path" "$link_path"
}

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

# Ensure per-user runtime directories exist (safe in packaged apps and across devices)
mkdir -p "$APP_SUPPORT_DIR" "$APP_LOG_DIR" "$APP_DATA_DIR" "$APP_DATA_LOG_DIR" "$SERVICE_LOG_DIR"
ok "Runtime directories ready"
log "App support dir: $APP_SUPPORT_DIR"
log "App logs dir: $APP_LOG_DIR"
log "Unified data dir: $APP_DATA_DIR"
log "Unified logs dir: $APP_DATA_LOG_DIR"
log "Python venv dir: $VENV"

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
bash "$AW_SCRIPT" >> "$AW_BOOTSTRAP_LOG" 2>&1 &
AW_PID=$!
PIDS+=("$AW_PID")
ok "ActivityWatch launched (PID $AW_PID)"
sleep 5

# STEP 5 - Check mac/ directory
if [ ! -d "$MAC_DIR" ]; then
  err "Could not find 'mac/' directory at: $MAC_DIR"
  exit 1
fi

# STEP 5.1 - Route all generated data into one folder
log "Linking data folders to unified storage..."
ensure_linked_dir "$MAC_DIR/details" "$APP_DATA_DIR/details"
ensure_linked_dir "$MAC_DIR/feedback" "$APP_DATA_DIR/feedback"
ensure_linked_dir "$MAC_DIR/interventions" "$APP_DATA_DIR/interventions"
ensure_linked_dir "$MAC_DIR/collated" "$APP_DATA_DIR/collated"
ensure_linked_dir "$MAC_DIR/logs" "$APP_DATA_DIR/logs_legacy"
ensure_linked_dir "$MAC_DIR/screenshot" "$APP_DATA_DIR/screenshot"

ensure_linked_dir "$SRC_DIR/watch" "$APP_DATA_DIR/watch"
ensure_linked_dir "$SRC_DIR/screenshot" "$APP_DATA_DIR/screenshot"
ensure_linked_dir "$SRC_DIR/activityTracker" "$APP_DATA_DIR/activityTracker"
ensure_linked_dir "$SRC_DIR/interventions" "$APP_DATA_DIR/interventions"
ensure_linked_dir "$SRC_DIR/details" "$APP_DATA_DIR/details"
ok "Unified data storage is ready"

# STEP 6 - Virtual environment
log "Checking virtual environment..."
if [ ! -f "$PYTHON" ]; then
  log "Creating .ilgc venv..."
  mkdir -p "$VENV"
  if ! "$PYTHON312" -m venv "$VENV"; then
    err "Failed to create virtual environment at $VENV"
    err "Check permissions for: $APP_SUPPORT_DIR"
    exit 1
  fi
fi
ok "Virtual environment ready"

# STEP 7 - Python dependencies
REQUIREMENTS="$MAC_DIR/requirements.txt"
if [ ! -f "$REQUIREMENTS" ]; then
  err "requirements.txt not found at $REQUIREMENTS"
  exit 1
fi

log "Checking Python dependencies..."
if ! "$PYTHON" -c "import flask, numpy, cv2" 2>/dev/null; then
  log "Installing Python dependencies..."
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Installing dependencies" >> "$PIP_LOG"
  if ! "$PYTHON" -m pip install --upgrade pip >> "$PIP_LOG" 2>&1; then
    err "Failed to upgrade pip. See: $PIP_LOG"
    exit 1
  fi
  if ! "$PYTHON" -m pip install -r "$REQUIREMENTS" >> "$PIP_LOG" 2>&1; then
    err "Failed to install Python dependencies. See: $PIP_LOG"
    exit 1
  fi
fi
if ! "$PYTHON" -c "import flask, numpy, cv2" 2>/dev/null; then
  err "Python dependencies still missing after install attempt. See: $PIP_LOG"
  exit 1
fi
ok "Python dependencies ready"

# Configure liblsl/pylsl before any watch imports
log "Configuring liblsl for pylsl..."
PYLSL_BUNDLED_DIR="$MAC_DIR/lib/pylsl"
PY_SITE_PACKAGES=$("$PYTHON" -c "import site; print(next((p for p in site.getsitepackages() if p.endswith('site-packages')), ''))" 2>/dev/null || true)
PYLSL_DEST_DYNAMIC=""
if [ -n "$PY_SITE_PACKAGES" ]; then
  PYLSL_DEST_DYNAMIC="$PY_SITE_PACKAGES/pylsl/lib"
  mkdir -p "$PYLSL_DEST_DYNAMIC"
fi

if [ -d "$PYLSL_BUNDLED_DIR" ] && [ -n "$PYLSL_DEST_DYNAMIC" ]; then
  cp -f "$PYLSL_BUNDLED_DIR"/liblsl*.dylib "$PYLSL_DEST_DYNAMIC"/ 2>/dev/null || true
fi

find_liblsl() {
  local candidate
  for candidate in \
    "$PYLSL_DEST_DYNAMIC/liblsl.dylib" \
    "$PYLSL_BUNDLED_DIR/liblsl.dylib" \
    "/opt/homebrew/lib/liblsl.dylib" \
    "/usr/local/lib/liblsl.dylib" \
    "/opt/homebrew/opt/lsl/lib/liblsl.dylib" \
    "/usr/local/opt/lsl/lib/liblsl.dylib" \
    "/opt/homebrew/opt/lsl/Frameworks/lsl.framework/Versions/A/lsl" \
    "/usr/local/opt/lsl/Frameworks/lsl.framework/Versions/A/lsl" \
    "/opt/homebrew/Cellar/lsl/1.17.4/Frameworks/lsl.framework/Versions/A/lsl"; do
    if [ -f "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done

  candidate=$(find /opt/homebrew /usr/local -type f -name "liblsl*.dylib" 2>/dev/null | head -n 1)
  if [ -n "$candidate" ]; then
    echo "$candidate"
    return 0
  fi

  return 1
}

PYLSL_LIB_PATH=""
PYLSL_LIB_PATH="$(find_liblsl || true)"

if [ -z "$PYLSL_LIB_PATH" ] && command -v brew &>/dev/null; then
  log "liblsl not found; installing Homebrew package lsl..."
  brew install labstreaminglayer/tap/lsl >> "$PIP_LOG" 2>&1 || brew install lsl >> "$PIP_LOG" 2>&1 || true
  PYLSL_LIB_PATH="$(find_liblsl || true)"
fi

if [ -n "$PYLSL_LIB_PATH" ] && [ -n "$PYLSL_DEST_DYNAMIC" ]; then
  cp -f "$PYLSL_LIB_PATH" "$PYLSL_DEST_DYNAMIC/liblsl.dylib" 2>/dev/null || true
  PYLSL_LIB_PATH="$PYLSL_DEST_DYNAMIC/liblsl.dylib"
fi

if [ -n "$PYLSL_LIB_PATH" ]; then
  export PYLSL_LIB="$PYLSL_LIB_PATH"
  LIB_DIR="$(dirname "$PYLSL_LIB_PATH")"
  if [ -n "$DYLD_LIBRARY_PATH" ]; then
    export DYLD_LIBRARY_PATH="$LIB_DIR:$DYLD_LIBRARY_PATH"
  else
    export DYLD_LIBRARY_PATH="$LIB_DIR"
  fi
  ok "liblsl configured: $PYLSL_LIB_PATH"
else
  warn "Could not locate liblsl.dylib; watch.py may fail to start"
fi

if ! "$PYTHON" -c "import pylsl" >> "$SERVICE_LOG_DIR/watch.log" 2>&1; then
  err "pylsl import failed. See: $SERVICE_LOG_DIR/watch.log"
  err "Expected lib location: $PYLSL_DEST_DYNAMIC"
  exit 1
fi
ok "pylsl import check passed"

# STEP 8 - Frontend dependencies
log "Checking frontend dependencies..."
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  log "Installing frontend dependencies..."
  cd "$FRONTEND_DIR" && npm install --silent
  cd "$SCRIPT_DIR"
fi
ok "Frontend dependencies ready"

# STEP 9 - Start Python backend services
log "Starting watch.py first..."
cd "$SRC_DIR"
"$PYTHON" watch.py >> "$SERVICE_LOG_DIR/watch.log" 2>&1 &
PID=$!; PIDS+=("$PID")
ok "watch.py started (PID $PID)"
sleep 2

# Wait until watch has at least two non-baseline samples with stress_level
log "Waiting for watch data readiness..."
WATCH_READY_TIMEOUT=90
WATCH_READY_COUNT=0
while [ $WATCH_READY_COUNT -lt $WATCH_READY_TIMEOUT ]; do
  if "$PYTHON" - <<'PY' "$APP_DATA_DIR/watch/watch_data.json"
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r") as f:
        data = json.load(f)
    entries = data.get("entries", []) if isinstance(data, dict) else []
    non_baseline_count = sum(
        isinstance(e, dict)
        and isinstance(e.get("watch_data"), dict)
        and e["watch_data"].get("is_baseline") is False
        and "stress_level" in e["watch_data"]
        for e in entries
    )
    ready = non_baseline_count >= 2
    raise SystemExit(0 if ready else 1)
except Exception:
    raise SystemExit(1)
PY
  then
    ok "Watch data is ready"
    break
  fi
  sleep 1
  WATCH_READY_COUNT=$((WATCH_READY_COUNT + 1))
done

if [ $WATCH_READY_COUNT -ge $WATCH_READY_TIMEOUT ]; then
  warn "Watch data not ready after ${WATCH_READY_TIMEOUT}s, continuing startup"
fi

log "Starting api_server.py..."
cd "$MAC_DIR"
"$PYTHON" api_server.py >> "$SERVICE_LOG_DIR/api_server.log" 2>&1 &
PID=$!; PIDS+=("$PID")
ok "api_server.py started (PID $PID)"
sleep 2

log "Starting client.py..."
cd "$SRC_DIR"
"$PYTHON" client.py >> "$SERVICE_LOG_DIR/client.log" 2>&1 &
PID=$!; PIDS+=("$PID")
ok "client.py started (PID $PID)"
sleep 1

if ! kill -0 "$PID" 2>/dev/null; then
  err "client.py exited immediately."
  err "This usually means camera permission is missing or camera init failed."
  err "Grant camera access, fully quit ILGC, and restart with ./start_mac.sh"
  if [ -f "$SERVICE_LOG_DIR/client.log" ]; then
    echo ""
    echo "Recent client.log:"
    tail -n 20 "$SERVICE_LOG_DIR/client.log" || true
  fi
  exit 1
fi

log "Starting collate_data.py..."
cd "$SRC_DIR"
"$PYTHON" collate_data.py >> "$SERVICE_LOG_DIR/collate_data.log" 2>&1 &
PID=$!; PIDS+=("$PID")
ok "collate_data.py started (PID $PID)"
sleep 1

if [ -f "$UTILS_DIR/run_activity.py" ]; then
  log "Starting run_activity.py..."
  cd "$SRC_DIR"
  "$PYTHON" "$UTILS_DIR/run_activity.py" >> "$SERVICE_LOG_DIR/run_activity.log" 2>&1 &
  PID=$!; PIDS+=("$PID")
  ok "run_activity.py started (PID $PID)"
  sleep 1
fi

# STEP 10 - Start frontend
log "Starting frontend (Vite)..."
cd "$FRONTEND_DIR"
npm run dev >> "$SERVICE_LOG_DIR/frontend.log" 2>&1 &
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
echo "Data folder   -> $APP_DATA_DIR"
echo "Service logs  -> $SERVICE_LOG_DIR"
echo ""
echo "Press Ctrl+C to stop everything."
echo ""

wait