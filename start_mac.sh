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
PID_FILE="$APP_DATA_DIR/ilgc_pids.txt"

# Calibration state file — watch.py writes this when baseline is saved.
# We gate collate_data.py and run_activity.py on it, but NOT api_server.
CALIBRATION_DONE_FILE="$APP_DATA_DIR/watch/baseline_calibration.json"

log()  { echo "[ILGC] $1"; }
ok()   { echo "[ILGC-OK] $1"; }
warn() { echo "[ILGC-WARN] $1"; }
err()  { echo "[ILGC-ERROR] $1"; }

ensure_linked_dir() {
  local link_path="$1" target_path="$2" backup_path
  mkdir -p "$target_path" "$(dirname "$link_path")"
  if [ -L "$link_path" ]; then
    [ "$(readlink "$link_path")" != "$target_path" ] && { rm -f "$link_path"; ln -s "$target_path" "$link_path"; }
    return
  fi
  if [ -d "$link_path" ]; then
    [ -n "$(ls -A "$link_path" 2>/dev/null)" ] && cp -a "$link_path"/. "$target_path"/ 2>/dev/null || true
    backup_path="${link_path}.legacy_$(date +%Y%m%d_%H%M%S)"
    mv "$link_path" "$backup_path"
  elif [ -e "$link_path" ]; then
    mv "$link_path" "${link_path}.legacy_$(date +%Y%m%d_%H%M%S)"
  fi
  ln -s "$target_path" "$link_path"
}

declare -a PIDS
register_pid() { PIDS+=("$1"); echo "$1" >> "$PID_FILE"; }

cleanup() {
  echo ""
  log "Shutting down all services..."
  for pid in "${PIDS[@]}"; do
    kill -TERM "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  done
  sleep 2
  for pid in "${PIDS[@]}"; do
    kill -KILL "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
  done
  pkill -f "api_server.py"    2>/dev/null || true
  pkill -f "watch.py"         2>/dev/null || true
  pkill -f "client.py"        2>/dev/null || true
  pkill -f "collate_data.py"  2>/dev/null || true
  pkill -f "run_activity.py"  2>/dev/null || true
  pkill -f "interventions.py" 2>/dev/null || true
  pkill -f "aw-qt"            2>/dev/null || true
  pkill -f "aw-server"        2>/dev/null || true
  pkill -f "aw-watcher"       2>/dev/null || true
  sleep 1
  pkill -9 -f "aw-qt"        2>/dev/null || true
  pkill -9 -f "aw-server"    2>/dev/null || true
  pkill -9 -f "aw-watcher"   2>/dev/null || true
  rm -f "$PID_FILE"
  ok "All services stopped."
  exit 0
}
trap cleanup SIGINT SIGTERM SIGHUP EXIT

echo ""
echo "ILGC Workplace and Distraction Monitor - Mac"
echo ""

mkdir -p "$APP_SUPPORT_DIR" "$APP_LOG_DIR" "$APP_DATA_DIR" "$APP_DATA_LOG_DIR" "$SERVICE_LOG_DIR"
> "$PID_FILE"
ok "Runtime directories ready"

start_service() {
  local name="$1" workdir="$2"; shift 2
  local logfile="$SERVICE_LOG_DIR/${name}.log"
  ( cd "$workdir"; exec "$@" >> "$logfile" 2>&1 ) &
  local pid=$!
  register_pid "$pid"
  ok "${name} started (PID $pid)"
  echo "$pid"
}

# ════════════════════════════════════════════════════════════════
# STEP 1 — System tools
# ════════════════════════════════════════════════════════════════
log "Checking Homebrew..."
if ! command -v brew &>/dev/null; then
  log "Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
[ -f "/opt/homebrew/bin/brew" ] && eval "$(/opt/homebrew/bin/brew shellenv)"
[ -f "/usr/local/bin/brew" ]    && eval "$(/usr/local/bin/brew shellenv)"
ok "Homebrew ready"

log "Checking Python 3.12..."
if ! command -v python3.12 &>/dev/null; then
  log "Installing Python 3.12..."
  brew install python@3.12
  export PATH="$(brew --prefix python@3.12)/bin:$PATH"
fi
PYTHON312="$(command -v python3.12)"
ok "Python 3.12 ready: $(python3.12 --version)"

log "Checking Node.js..."
if ! command -v node &>/dev/null; then
  brew install node
fi
ok "Node.js ready: $(node --version)"

# Informational only — no osascript to avoid triggering repeated permission dialogs
log "Reminder: ActivityWatch needs Accessibility + Screen Recording."
log "  System Settings > Privacy & Security > Accessibility > ActivityWatch"

# ════════════════════════════════════════════════════════════════
# STEP 2 — ActivityWatch
# ════════════════════════════════════════════════════════════════
AW_SCRIPT="$UTILS_DIR/mac.sh"
[ ! -f "$AW_SCRIPT" ] && { err "utils/mac.sh not found"; exit 1; }
log "Launching ActivityWatch..."
chmod +x "$AW_SCRIPT"
( bash "$AW_SCRIPT" >> "$AW_BOOTSTRAP_LOG" 2>&1 ) &
AW_PID=$!; register_pid "$AW_PID"
ok "ActivityWatch launched (PID $AW_PID)"

AW_WAIT=0
while [ $AW_WAIT -lt 60 ]; do
  curl -s http://localhost:5600/api/0/buckets > /dev/null 2>&1 && { ok "ActivityWatch server ready after ${AW_WAIT}s"; break; }
  sleep 2; AW_WAIT=$((AW_WAIT + 2))
done
[ $AW_WAIT -ge 60 ] && warn "ActivityWatch server did not respond within 60s"

# ════════════════════════════════════════════════════════════════
# STEP 3 — Data directories + venv + deps + liblsl
# ════════════════════════════════════════════════════════════════
[ ! -d "$MAC_DIR" ] && { err "mac/ directory not found at $MAC_DIR"; exit 1; }

log "Linking data folders..."
ensure_linked_dir "$MAC_DIR/details"       "$APP_DATA_DIR/details"
ensure_linked_dir "$MAC_DIR/feedback"      "$APP_DATA_DIR/feedback"
ensure_linked_dir "$MAC_DIR/interventions" "$APP_DATA_DIR/interventions"
ensure_linked_dir "$MAC_DIR/collated"      "$APP_DATA_DIR/collated"
ensure_linked_dir "$MAC_DIR/logs"          "$APP_DATA_DIR/logs_legacy"
ensure_linked_dir "$MAC_DIR/screenshot"    "$APP_DATA_DIR/screenshot"
ensure_linked_dir "$SRC_DIR/watch"           "$APP_DATA_DIR/watch"
ensure_linked_dir "$SRC_DIR/screenshot"      "$APP_DATA_DIR/screenshot"
ensure_linked_dir "$SRC_DIR/activityTracker" "$APP_DATA_DIR/activityTracker"
ensure_linked_dir "$SRC_DIR/interventions"   "$APP_DATA_DIR/interventions"
ensure_linked_dir "$SRC_DIR/details"         "$APP_DATA_DIR/details"
ok "Data directories ready"

log "Checking virtual environment..."
if [ ! -f "$PYTHON" ]; then
  log "Creating venv at $VENV..."
  mkdir -p "$VENV"
  "$PYTHON312" -m venv "$VENV" || { err "Failed to create venv"; exit 1; }
fi
ok "Virtual environment ready"

REQUIREMENTS="$MAC_DIR/requirements.txt"
[ ! -f "$REQUIREMENTS" ] && { err "requirements.txt not found"; exit 1; }
log "Checking Python dependencies..."
if ! "$PYTHON" -c "import flask, numpy, cv2" 2>/dev/null; then
  log "Installing Python dependencies (first run)..."
  "$PYTHON" -m pip install --upgrade pip >> "$PIP_LOG" 2>&1 || true
  "$PYTHON" -m pip install -r "$REQUIREMENTS" >> "$PIP_LOG" 2>&1 || { err "pip install failed. See $PIP_LOG"; exit 1; }
fi
ok "Python dependencies ready"

# Camera check
CAMERA_AVAILABLE=false
if "$PYTHON" -c "import cv2,sys; cap=cv2.VideoCapture(0); ok=cap.isOpened(); cap.release(); sys.exit(0 if ok else 1)" 2>/dev/null; then
  CAMERA_AVAILABLE=true; ok "Camera accessible"
else
  warn "Camera not accessible — screenshot-only mode."
fi

# liblsl
log "Configuring liblsl..."
PYLSL_BUNDLED_DIR="$MAC_DIR/lib/pylsl"
PY_SITE_PACKAGES=$("$PYTHON" -c "import site; print(next((p for p in site.getsitepackages() if p.endswith('site-packages')), ''))" 2>/dev/null || true)
PYLSL_DEST_DYNAMIC=""
[ -n "$PY_SITE_PACKAGES" ] && { PYLSL_DEST_DYNAMIC="$PY_SITE_PACKAGES/pylsl/lib"; mkdir -p "$PYLSL_DEST_DYNAMIC"; }
[ -d "$PYLSL_BUNDLED_DIR" ] && [ -n "$PYLSL_DEST_DYNAMIC" ] && cp -f "$PYLSL_BUNDLED_DIR"/liblsl*.dylib "$PYLSL_DEST_DYNAMIC"/ 2>/dev/null || true

find_liblsl() {
  for c in "$PYLSL_DEST_DYNAMIC/liblsl.dylib" "$PYLSL_BUNDLED_DIR/liblsl.dylib" \
            "/opt/homebrew/lib/liblsl.dylib" "/usr/local/lib/liblsl.dylib" \
            "/opt/homebrew/opt/lsl/lib/liblsl.dylib" "/usr/local/opt/lsl/lib/liblsl.dylib"; do
    [ -f "$c" ] && { echo "$c"; return 0; }
  done
  c=$(find /opt/homebrew /usr/local -name "liblsl*.dylib" 2>/dev/null | head -1)
  [ -n "$c" ] && { echo "$c"; return 0; }; return 1
}

PYLSL_LIB_PATH="$(find_liblsl 2>/dev/null || true)"
if [ -z "$PYLSL_LIB_PATH" ] && command -v brew &>/dev/null; then
  log "Installing liblsl via brew..."
  brew install labstreaminglayer/tap/lsl >> "$PIP_LOG" 2>&1 || brew install lsl >> "$PIP_LOG" 2>&1 || true
  PYLSL_LIB_PATH="$(find_liblsl 2>/dev/null || true)"
fi
if [ -n "$PYLSL_LIB_PATH" ] && [ -n "$PYLSL_DEST_DYNAMIC" ]; then
  cp -f "$PYLSL_LIB_PATH" "$PYLSL_DEST_DYNAMIC/liblsl.dylib" 2>/dev/null || true
  PYLSL_LIB_PATH="$PYLSL_DEST_DYNAMIC/liblsl.dylib"
fi
if [ -n "$PYLSL_LIB_PATH" ]; then
  export PYLSL_LIB="$PYLSL_LIB_PATH"
  export DYLD_LIBRARY_PATH="$(dirname "$PYLSL_LIB_PATH")${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
  ok "liblsl: $PYLSL_LIB_PATH"
else
  warn "liblsl not found — watch.py may fail"
fi
"$PYTHON" -c "import pylsl" >> "$SERVICE_LOG_DIR/watch.log" 2>&1 || { err "pylsl import failed"; exit 1; }

log "Checking frontend dependencies..."
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  cd "$FRONTEND_DIR" && npm install --silent; cd "$SCRIPT_DIR"
fi
ok "Frontend dependencies ready"

# ════════════════════════════════════════════════════════════════
# STEP 4 — START WATCH CALIBRATION FIRST
# All other services wait until baseline is confirmed.
# The Electron loading screen shows calibration progress via the
# stdout lines we emit here (picked up by runStartScript in main.js).
# ════════════════════════════════════════════════════════════════

# Clear any stale baseline so we know when THIS session's calibration
# finishes (watch.py will re-write it).
rm -f "$CALIBRATION_DONE_FILE"

log "Starting watch.py — calibration is required before other services start."
start_service "watch" "$SRC_DIR" "$PYTHON" watch.py > /dev/null

CALIB_TOTAL=60   # watch.py BASELINE_DURATION constant
CALIB_POLL=5
CALIB_ELAPSED=0
CALIB_MAX=$((CALIB_TOTAL + 60))   # give up to 2 min total (60s calibration + 60s buffer)

echo "Calibrating smartwatch — keep the watch on your wrist (up to ${CALIB_TOTAL}s)"

while [ $CALIB_ELAPSED -lt $CALIB_MAX ]; do
  if [ -f "$CALIBRATION_DONE_FILE" ]; then
    ok "Smartwatch calibration complete"
    break
  fi

  sleep $CALIB_POLL
  CALIB_ELAPSED=$((CALIB_ELAPSED + CALIB_POLL))

  if [ $CALIB_ELAPSED -le $CALIB_TOTAL ]; then
    REMAINING=$((CALIB_TOTAL - CALIB_ELAPSED))
    echo "Calibrating smartwatch — ${REMAINING}s remaining, keep watch on your wrist…"
  else
    echo "Calibrating smartwatch — finalising baseline, almost done…"
  fi
done

if [ ! -f "$CALIBRATION_DONE_FILE" ]; then
  warn "Smartwatch calibration timed out — watch may not be connected or in range."
  warn "HRV-based stress features will be unavailable this session."
  warn "All other features (screen monitoring, interventions) will work normally."
fi

# ════════════════════════════════════════════════════════════════
# STEP 5 — START api_server (now that calibration is done/skipped)
# Electron begins polling port 5002 from the moment runStartScript
# resolves — which happens after "All services running" below.
# So the API just needs to be up before we print that line.
# ════════════════════════════════════════════════════════════════
log "Starting api_server.py..."
start_service "api_server" "$MAC_DIR" "$PYTHON" api_server.py > /dev/null
sleep 1

log "Waiting for API server on port 5002..."
API_WAIT=0
while [ $API_WAIT -lt 30 ]; do
  curl -s http://localhost:5002/api/health > /dev/null 2>&1 && { ok "API server ready after ${API_WAIT}s"; break; }
  sleep 1; API_WAIT=$((API_WAIT + 1))
done
[ $API_WAIT -ge 30 ] && { err "API server did not start within 30 seconds"; exit 1; }

# ════════════════════════════════════════════════════════════════
# STEP 6 — Remaining services (camera, collation, activity, frontend)
# ════════════════════════════════════════════════════════════════
log "Starting client.py..."
client_pid=$(start_service "client" "$SRC_DIR" "$PYTHON" client.py)
sleep 3
if ! kill -0 "$client_pid" 2>/dev/null; then
  warn "client.py exited — camera permission likely missing."
  warn "System Settings > Privacy & Security > Camera > enable ILGC Research, then restart."
else
  ok "client.py running"
fi

log "Starting collate_data.py..."
start_service "collate_data" "$SRC_DIR" "$PYTHON" collate_data.py > /dev/null
sleep 1

if [ -f "$UTILS_DIR/run_activity.py" ]; then
  log "Starting run_activity.py..."
  start_service "run_activity" "$SRC_DIR" "$PYTHON" "$UTILS_DIR/run_activity.py" > /dev/null
  sleep 1
fi

log "Starting frontend (Vite)..."
start_service "frontend" "$FRONTEND_DIR" npm run dev > /dev/null

log "Waiting for frontend on port 8080..."
FE_WAIT=0
while [ $FE_WAIT -lt 30 ]; do
  curl -s http://localhost:8080 > /dev/null 2>&1 && { ok "Frontend ready"; break; }
  sleep 1; FE_WAIT=$((FE_WAIT + 1))
done

# ════════════════════════════════════════════════════════════════
# STEP 7 — Signal Electron (this exact string is watched in main.js)
# ════════════════════════════════════════════════════════════════
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