#!/bin/bash
set -e

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

VERSION="v0.13.2"
BASE_URL="https://github.com/ActivityWatch/activitywatch/releases/download/${VERSION}"

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

AppName="ActivityWatch.app"
AppPath="$DMGVolume/$AppName"

if [ ! -d "$AppPath" ]; then
  echo "$AppName not found in mounted volume: $DMGVolume"
  echo "Available contents:"
  ls -la "$DMGVolume"
  hdiutil detach "$DMGVolume"
  exit 1
fi

if [ -d "/Applications/$AppName" ]; then
  echo "Removing old $AppName..."
  rm -rf "/Applications/$AppName"
fi

echo "Copying $AppName to /Applications..."
cp -R "$AppPath" /Applications/

echo "Unmounting DMG..."
hdiutil detach "$DMGVolume"

# Remove Gatekeeper quarantine flag
echo "Removing quarantine flag..."
xattr -dr com.apple.quarantine "/Applications/$AppName" 2>/dev/null || true

echo "Launching ActivityWatch..."
open "/Applications/$AppName"
sleep 3

cd /Applications/ActivityWatch.app/Contents/MacOS/
./aw-qt