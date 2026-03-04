@echo off
setlocal EnableDelayedExpansion

set VERSION=v0.13.2
set BASE_URL=https://github.com/ActivityWatch/activitywatch/releases/download/%VERSION%
set AppPath=%LOCALAPPDATA%\activitywatch\activitywatch.exe
set FILE=activitywatch-%VERSION%-windows-x86_64-setup.exe
set URL=%BASE_URL%/%FILE%

:: ── Free port 5600 if anything is holding it ──────────────────────
echo Checking port 5600...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5600 "') do (
  echo Port 5600 in use by PID %%a — killing...
  taskkill /PID %%a /F >nul 2>&1
)
echo Port 5600 freed.

:: ── Check if already installed ────────────────────────────────────
if exist "%AppPath%" (
  echo ActivityWatch is already installed. Skipping download.
  goto LAUNCH
)

:: ── Download and install ──────────────────────────────────────────
echo ActivityWatch not found. Installing...
if not exist activitywatch-install mkdir activitywatch-install
cd activitywatch-install

echo Downloading ActivityWatch for Windows...
curl -L -o "%FILE%" "%URL%"
if errorlevel 1 (
  echo Download failed. Check your internet connection.
  pause
  exit /b 1
)

echo Running installer — follow the prompts...
:: /S flag attempts a silent install; remove it if you want the GUI installer
start /wait "" "%FILE%" /S
if errorlevel 1 (
  echo Installer failed or was cancelled.
  pause
  exit /b 1
)
echo Installation complete.
cd ..

:: ── Launch ────────────────────────────────────────────────────────
:LAUNCH
echo Launching ActivityWatch...
start "" "%AppPath%"

echo ActivityWatch is running.
echo Close this window or press Ctrl+C to stop ActivityWatch.

:: Keep window open and wait — kill AW when this window is closed
:WAIT
timeout /t 5 /nobreak >nul
tasklist /FI "IMAGENAME eq activitywatch.exe" 2>nul | find /i "activitywatch.exe" >nul
if errorlevel 1 (
  echo ActivityWatch process ended.
  goto END
)
goto WAIT

:END
echo Stopping ActivityWatch...
taskkill /IM "activitywatch.exe" /F >nul 2>&1
taskkill /IM "aw-server.exe" /F >nul 2>&1
taskkill /IM "aw-watcher-window.exe" /F >nul 2>&1
taskkill /IM "aw-watcher-afk.exe" /F >nul 2>&1
echo Done.
pause