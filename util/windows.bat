@echo off
set VERSION=v0.13.2
set BASE_URL=https://github.com/ActivityWatch/activitywatch/releases/download/%VERSION%

mkdir activitywatch-install
cd activitywatch-install

set FILE=activitywatch-%VERSION%-windows-x86_64-setup.exe
set URL=%BASE_URL%/%FILE%

echo Downloading ActivityWatch for Windows...
curl -L -o %FILE% %URL%

echo Starting installer...
start %FILE%
