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
  echo Port 5600 in use by PID %%a - killing...
  taskkill /PID %%a /F >nul 2>&1
)
echo Port 5600 is free.

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
  exit /b 1
)

echo Running silent installer...
start /wait "" "%FILE%" /S
if errorlevel 1 (
  echo Installer failed or was cancelled.
  exit /b 1
)
echo Installation complete.
cd ..

:: ── Launch ────────────────────────────────────────────────────────
:LAUNCH
echo Launching ActivityWatch...
start "" "%AppPath%"

:: Wait for server to respond
echo Waiting for ActivityWatch server...
set /a AW_WAIT=0
:WAIT_SERVER
curl -s http://localhost:5600/api/0/info >nul 2>&1
if not errorlevel 1 (
    echo ActivityWatch server ready after !AW_WAIT!s
    goto CHECK_BUCKETS
)
timeout /t 1 /nobreak >nul
set /a AW_WAIT+=1
if !AW_WAIT! geq 45 goto CHECK_BUCKETS
goto WAIT_SERVER

:CHECK_BUCKETS
:: Wait for watcher buckets (window + afk)
echo Verifying watcher buckets registered...
set /a BUCKET_WAIT=0
:BUCKET_LOOP
curl -s http://localhost:5600/api/0/buckets 2>nul | findstr /c:"aw-watcher-window" >nul
if errorlevel 1 goto BUCKET_WAIT_MORE
curl -s http://localhost:5600/api/0/buckets 2>nul | findstr /c:"aw-watcher-afk" >nul
if errorlevel 1 goto BUCKET_WAIT_MORE
echo Watcher buckets registered after !BUCKET_WAIT!s
goto AW_RUNNING

:BUCKET_WAIT_MORE
timeout /t 2 /nobreak >nul
set /a BUCKET_WAIT+=2
if !BUCKET_WAIT! geq 60 (
    echo WARNING: Watcher buckets did not register within 60s.
    echo   ActivityWatch may need a one-time permission approval.
    goto AW_RUNNING
)
goto BUCKET_LOOP

:AW_RUNNING
echo ActivityWatch running. Watchers active.

:: Keep window alive until AW stops or this script is killed
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
exit /b 0
