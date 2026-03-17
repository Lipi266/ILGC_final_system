@echo off
:: ─────────────────────────────────────────────────────────────
:: ILGC Windows Stop Script
:: Kills all services started by start_windows.bat
:: ─────────────────────────────────────────────────────────────

echo.
echo [ILGC] Stopping all ILGC services...

:: Kill Python processes running ILGC scripts
echo [ILGC] Stopping Python services...
taskkill /FI "WINDOWTITLE eq ILGC api_server*"   /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq ILGC watch*"         /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq ILGC client*"        /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq ILGC collate_data*"  /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq ILGC run_activity*"  /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq ILGC frontend*"      /F >nul 2>&1

:: Stop ActivityWatch
echo [ILGC] Stopping ActivityWatch...
taskkill /FI "WINDOWTITLE eq ActivityWatch*" /F >nul 2>&1
taskkill /IM "activitywatch.exe"  /F >nul 2>&1
taskkill /IM "aw-server.exe"      /F >nul 2>&1
taskkill /IM "aw-watcher-window.exe" /F >nul 2>&1
taskkill /IM "aw-watcher-afk.exe" /F >nul 2>&1

:: Free port 5600 in case AW left it occupied
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5600 "') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: Free port 5000 (api_server)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5000 "') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo [ILGC] All services stopped. Goodbye!
timeout /t 2 /nobreak >nul