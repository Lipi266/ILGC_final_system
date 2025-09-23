#!/bin/bash
set -e

VERSION="v0.13.2"
BASE_URL="https://github.com/ActivityWatch/activitywatch/releases/download/${VERSION}"

mkdir -p activitywatch-install
cd activitywatch-install || exit

FILE="activitywatch-${VERSION}-linux-x86_64.zip"
URL="${BASE_URL}/${FILE}"

echo "Downloading ActivityWatch for Linux..."
curl -L -o "$FILE" "$URL"
unzip -o "$FILE" -d activitywatch
cd activitywatch

echo "Starting ActivityWatch..."
./aw-qt
