#!/bin/bash
set -e

# ── Cleanup function — kills all AW processes on exit/Ctrl+C ──────
cleanup() {
  echo ""
  echo "Shutting down ActivityWatch..."
  pkill -f "aw-qt"      2>/dev/null || true
  pkill -f "aw-server"  2>/dev/null || true
  pkill -f "aw-watcher" 2>/dev/null || true
  sleep 1
  pkill -9 -f "aw-qt"      2>/dev/null || true
  pkill -9 -f "aw-server"  2>/dev/null || true
  pkill -9 -f "aw-watcher" 2>/dev/null || true
  echo "ActivityWatch stopped."
  exit 0
}

trap cleanup SIGINT SIGTERM SIGHUP EXIT

AW_STATE_DIR="$HOME/Library/Application Support/activitywatch"
AW_SERVER_DIR="$AW_STATE_DIR/aw-server"

# Repair broken state where aw-server exists as a file, which crashes aw-server startup.
if [ -f "$AW_SERVER_DIR" ]; then
  echo "Found invalid file at $AW_SERVER_DIR; moving it aside."
  mv "$AW_SERVER_DIR" "${AW_SERVER_DIR}.backup_$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "$AW_SERVER_DIR"

# ── Free port 5600 if anything is still holding it ────────────────
echo "Checking port 5600..."
PIDS=$(lsof -ti :5600 2>/dev/null || true)
if [ -n "$PIDS" ]; then
  echo "Port 5600 in use by PID(s): $PIDS — killing..."
  echo "$PIDS" | xargs kill -9 2>/dev/null || true
  sleep 1
  echo "Port 5600 freed."
else
  echo "Port 5600 is free."
fi

AppName="ActivityWatch.app"
VERSION="v0.13.2"
BASE_URL="https://github.com/ActivityWatch/activitywatch/releases/download/${VERSION}"

# ── Check if ActivityWatch is already installed ───────────────────
if [ -d "/Applications/$AppName" ]; then
  echo "ActivityWatch is already installed at /Applications/$AppName"
  echo "Skipping download and install — launching directly."
else
  echo "ActivityWatch not found. Installing..."

  mkdir -p activitywatch-install
  cd activitywatch-install || exit

  FILE="activitywatch-${VERSION}-macos-x86_64.dmg"
  URL="${BASE_URL}/${FILE}"

  echo "Downloading ActivityWatch for macOS..."
  curl -L -o "$FILE" "$URL"
  echo "Downloaded: $FILE"

  echo "Mounting $FILE..."
  hdiutil attach "$FILE" -nobrowse

  DMGVolume=$(hdiutil info | grep "/Volumes/ActivityWatch" | awk -F'\t' '{print $3}' | head -1)
  if [ -z "$DMGVolume" ]; then
    echo "Failed to find mounted ActivityWatch volume"
    exit 1
  fi
  echo "Found mounted volume: $DMGVolume"

  AppPath="$DMGVolume/$AppName"
  if [ ! -d "$AppPath" ]; then
    echo "$AppName not found in mounted volume: $DMGVolume"
    echo "Available contents:"
    ls -la "$DMGVolume"
    hdiutil detach "$DMGVolume"
    exit 1
  fi

  echo "Copying $AppName to /Applications..."
  cp -R "$AppPath" /Applications/

  echo "Unmounting DMG..."
  hdiutil detach "$DMGVolume"

  echo "Removing quarantine flag..."
  xattr -dr com.apple.quarantine "/Applications/$AppName" 2>/dev/null || true

  echo "Installation complete."
fi

# ── Launch ────────────────────────────────────────────────────────
AW_APP_DIR="/Applications/ActivityWatch.app/Contents/MacOS"

echo "Launching ActivityWatch..."
"$AW_APP_DIR/aw-qt" &
AW_PID=$!

# Wait for server to be ready
echo "Waiting for ActivityWatch server to start..."
for i in $(seq 1 30); do
  if curl -s http://localhost:5600/api/0/info > /dev/null 2>&1; then
    echo "ActivityWatch server ready after ${i}s"
    break
  fi
  sleep 1
done

# Explicitly start watchers with full absolute paths
# (Required when launched from Electron DMG — relative paths fail)
echo "Starting ActivityWatch watchers..."
"$AW_APP_DIR/aw-watcher-afk" &
sleep 2
"$AW_APP_DIR/aw-watcher-window" &
sleep 2

echo "Verifying watcher buckets registered..."
for i in $(seq 1 30); do
  BUCKETS=$(curl -s http://localhost:5600/api/0/buckets 2>/dev/null || echo "{}")
  if echo "$BUCKETS" | grep -q "aw-watcher"; then
    echo "Watcher buckets registered after ${i}s"
    break
  fi
  sleep 1
done

echo "ActivityWatch running (PID $AW_PID). Watchers active. Press Ctrl+C to stop."
wait $AW_PID