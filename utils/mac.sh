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

# Repair broken state where aw-server exists as a file
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

AW_APP_DIR="/Applications/ActivityWatch.app/Contents/MacOS"

# ── Launch aw-qt ONLY — it manages all watchers internally ────────
# DO NOT launch aw-watcher-window or aw-watcher-afk separately.
# Doing so causes "Another instance is already running" errors, and
# the separately-launched watchers fail because they inherit the wrong
# process identity for Accessibility/Screen Recording permissions.
# The watchers bundled inside aw-qt carry the correct entitlements.
echo "Launching ActivityWatch (aw-qt manages all watchers)..."
# Launch detached via `open` so ActivityWatch runs under its own bundle
# identity — otherwise macOS TCC attributes Accessibility/Screen Recording
# requests to the parent (ILGC Research / Electron), causing a repeated
# permission prompt and "unknown" window titles.
open -gja "ActivityWatch"
AW_PID=""

# ── Wait for HTTP server to respond ───────────────────────────────
echo "Waiting for ActivityWatch server to start..."
for i in $(seq 1 45); do
  if curl -s http://localhost:5600/api/0/info > /dev/null 2>&1; then
    echo "ActivityWatch server ready after ${i}s"
    break
  fi
  sleep 1
done

# ── Wait for watcher buckets (registered by aw-qt's internal watchers)
# We do NOT start watchers ourselves — just wait for aw-qt to register them.
echo "Verifying watcher buckets registered..."
BUCKET_WAIT=0
BUCKET_MAX=60
while [ $BUCKET_WAIT -lt $BUCKET_MAX ]; do
  BUCKETS=$(curl -s http://localhost:5600/api/0/buckets 2>/dev/null || echo "{}")
  WIN_BUCKET=$(echo "$BUCKETS" | grep -o '"aw-watcher-window[^"]*"' | head -1 | tr -d '"' || true)
  AFK_BUCKET=$(echo "$BUCKETS" | grep -o '"aw-watcher-afk[^"]*"' | head -1 | tr -d '"' || true)

  if [ -n "$WIN_BUCKET" ] && [ -n "$AFK_BUCKET" ]; then
    echo "Watcher buckets registered after ${BUCKET_WAIT}s"
    echo "  Window bucket : $WIN_BUCKET"
    echo "  AFK bucket    : $AFK_BUCKET"
    break
  fi

  sleep 2
  BUCKET_WAIT=$((BUCKET_WAIT + 2))

  if [ $((BUCKET_WAIT % 10)) -eq 0 ]; then
    echo "  Still waiting for watcher buckets... (${BUCKET_WAIT}s)"
    # Log which buckets exist so far
    echo "$BUCKETS" | grep -o '"aw-[^"]*"' | tr -d '"' | while read -r b; do echo "    found: $b"; done
  fi
done

if [ $BUCKET_WAIT -ge $BUCKET_MAX ]; then
  echo "WARNING: Watcher buckets did not register within ${BUCKET_MAX}s."
  echo "  This usually means Accessibility or Screen Recording permission"
  echo "  has not been granted to ActivityWatch."
  echo ""
  echo "  To fix: Open System Settings > Privacy & Security > Accessibility"
  echo "  and enable ActivityWatch. Then quit ILGC and reopen it."
  echo ""
  echo "  Continuing without confirmed window tracking..."
else
  echo "ActivityWatch running. Watchers active. Press Ctrl+C to stop."
fi

# Keep this script alive so the parent (start_mac.sh) treats AW as running.
# aw-qt runs detached under its own bundle; we poll its HTTP server instead.
while curl -s http://localhost:5600/api/0/info > /dev/null 2>&1; do
  sleep 5
done