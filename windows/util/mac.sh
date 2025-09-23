#!/bin/bash
set -e

VERSION="v0.13.2"
BASE_URL="https://github.com/ActivityWatch/activitywatch/releases/download/${VERSION}"

mkdir -p activitywatch-install
cd activitywatch-install || exit

FILE="activitywatch-${VERSION}-macos-x86_64.dmg"
URL="${BASE_URL}/${FILE}"

echo "Downloading ActivityWatch for macOS..."
curl -L -o "$FILE" "$URL"
echo "Downloaded: $FILE"

DMG_FILE="$FILE"

echo "Mounting $DMG_FILE..."
hdiutil attach "$DMG_FILE" -nobrowse

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

echo "Launching ActivityWatch..."
open "/Applications/$AppName"

cd /Applications/ActivityWatch.app/Contents/MacOS/
./aw-qt
