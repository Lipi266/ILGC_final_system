@echo off
setlocal EnableDelayedExpansion

:: ─────────────────────────────────────────────────────────────
:: ILGC Windows Launcher — parity with start_mac.sh
:: Calibration-first, per-service log files, health polling.
:: ─────────────────────────────────────────────────────────────

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "WIN_DIR=%SCRIPT_DIR%\windows"
set "SRC_DIR=%WIN_DIR%\src"
set "UTILS_DIR=%SCRIPT_DIR%\utils"
set "FRONTEND_DIR=%WIN_DIR%\frontend"
set "APP_NAME=ILGC Research"
set "APP_SUPPORT_DIR=%APPDATA%\%APP_NAME%"
set "APP_DATA_DIR=%APP_SUPPORT_DIR%\data"
set "APP_DATA_LOG_DIR=%APP_DATA_DIR%\logs"
set "SERVICE_LOG_DIR=%APP_DATA_LOG_DIR%\services"
set "VENV=%APP_SUPPORT_DIR%\venvs\windows"
set "PYTHON=%VENV%\Scripts\python.exe"
set "PID_FILE=%APP_DATA_DIR%\ilgc_pids.txt"
set "CALIBRATION_DONE_FILE=%APP_DATA_DIR%\watch\baseline_calibration.json"
set "AW_BOOTSTRAP_LOG=%APP_DATA_LOG_DIR%\activitywatch_bootstrap.log"
set "PIP_LOG=%APP_DATA_LOG_DIR%\pip_install.log"

if not exist "%APP_SUPPORT_DIR%"   mkdir "%APP_SUPPORT_DIR%"
if not exist "%APP_DATA_DIR%"      mkdir "%APP_DATA_DIR%"
if not exist "%APP_DATA_LOG_DIR%"  mkdir "%APP_DATA_LOG_DIR%"
if not exist "%SERVICE_LOG_DIR%"   mkdir "%SERVICE_LOG_DIR%"
if not exist "%APP_DATA_DIR%\watch" mkdir "%APP_DATA_DIR%\watch"
type nul > "%PID_FILE%"

echo.
echo ILGC Workplace and Distraction Monitor - Windows
echo.
echo [ILGC-OK] Runtime directories ready

:: ════════════════════════════════════════════════════════════
:: STEP 1 — Python 3.12
:: ════════════════════════════════════════════════════════════
echo [ILGC] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ILGC] Installing Python 3.12 via winget...
    winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements >nul 2>&1
    if errorlevel 1 (
        echo [ILGC-ERROR] Could not install Python. Install manually from https://www.python.org/downloads/
        exit /b 1
    )
    call :RefreshPath
    python --version >nul 2>&1
    if errorlevel 1 (
        echo [ILGC-ERROR] Python still not found after install. Restart and try again.
        exit /b 1
    )
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [ILGC-OK] %%v

:: ════════════════════════════════════════════════════════════
:: STEP 2 — Node.js
:: ════════════════════════════════════════════════════════════
echo [ILGC] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [ILGC] Installing Node.js via winget...
    winget install -e --id OpenJS.NodeJS --silent --accept-package-agreements --accept-source-agreements >nul 2>&1
    if errorlevel 1 (
        echo [ILGC-ERROR] Could not install Node.js. Install manually from https://nodejs.org/
        exit /b 1
    )
    call :RefreshPath
    node --version >nul 2>&1
    if errorlevel 1 (
        echo [ILGC-ERROR] Node.js still not found after install.
        exit /b 1
    )
)
for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo [ILGC-OK] Node.js %%v

:: ════════════════════════════════════════════════════════════
:: STEP 3 — ActivityWatch
:: ════════════════════════════════════════════════════════════
set "AW_SCRIPT=%UTILS_DIR%\windows.bat"
if not exist "%AW_SCRIPT%" (
    echo [ILGC-ERROR] utils\windows.bat not found
    exit /b 1
)
echo [ILGC] Launching ActivityWatch...
start "ActivityWatch" /min cmd /c ""%AW_SCRIPT%" >> "%AW_BOOTSTRAP_LOG%" 2>&1"

set /a AW_WAIT=0
:WAIT_AW
curl -s http://localhost:5600/api/0/buckets >nul 2>&1
if not errorlevel 1 (
    echo [ILGC-OK] ActivityWatch server ready after !AW_WAIT!s
    goto AW_READY
)
timeout /t 2 /nobreak >nul
set /a AW_WAIT+=2
if !AW_WAIT! geq 60 (
    echo [ILGC-WARN] ActivityWatch server did not respond within 60s
    goto AW_READY
)
goto WAIT_AW
:AW_READY

:: ════════════════════════════════════════════════════════════
:: STEP 4 — venv
:: ════════════════════════════════════════════════════════════
if not exist "%PYTHON%" (
    echo [ILGC] Creating venv at %VENV%...
    if not exist "%APP_SUPPORT_DIR%\venvs" mkdir "%APP_SUPPORT_DIR%\venvs"
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo [ILGC-ERROR] Failed to create virtual environment
        exit /b 1
    )
)
echo [ILGC-OK] Virtual environment ready

:: ════════════════════════════════════════════════════════════
:: STEP 5 — Python dependencies
:: ════════════════════════════════════════════════════════════
set "REQUIREMENTS=%WIN_DIR%\requirements.txt"
if not exist "%REQUIREMENTS%" (
    echo [ILGC-ERROR] requirements.txt not found at %REQUIREMENTS%
    exit /b 1
)
"%PYTHON%" -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [ILGC] Installing Python dependencies (first run)...
    "%PYTHON%" -m pip install --upgrade pip >> "%PIP_LOG%" 2>&1
    "%PYTHON%" -m pip install -r "%REQUIREMENTS%" >> "%PIP_LOG%" 2>&1
    if errorlevel 1 (
        echo [ILGC-ERROR] pip install failed. See %PIP_LOG%
        exit /b 1
    )
)
echo [ILGC-OK] Python dependencies ready

:: ════════════════════════════════════════════════════════════
:: STEP 6 — Frontend dependencies
:: ════════════════════════════════════════════════════════════
if not exist "%FRONTEND_DIR%\node_modules" (
    echo [ILGC] Installing frontend dependencies (first run)...
    pushd "%FRONTEND_DIR%"
    call npm install --silent
    popd
)
echo [ILGC-OK] Frontend dependencies ready

:: ════════════════════════════════════════════════════════════
:: STEP 7 — Watch calibration BEFORE starting API
:: ════════════════════════════════════════════════════════════
if exist "%CALIBRATION_DONE_FILE%" del /f /q "%CALIBRATION_DONE_FILE%" >nul 2>&1

echo [ILGC] Starting watch.py - calibration required before other services.
start "ILGC watch" /min cmd /c ""%PYTHON%" "%SRC_DIR%\watch.py" >> "%SERVICE_LOG_DIR%\watch.log" 2>&1"

set /a CALIB_ELAPSED=0
set /a CALIB_TOTAL=60
set /a CALIB_MAX=120
echo Calibrating smartwatch - keep the watch on your wrist (up to %CALIB_TOTAL%s)

:CALIB_LOOP
if exist "%CALIBRATION_DONE_FILE%" (
    echo [ILGC-OK] Smartwatch calibration complete
    goto CALIB_DONE
)
timeout /t 5 /nobreak >nul
set /a CALIB_ELAPSED+=5
if !CALIB_ELAPSED! leq !CALIB_TOTAL! (
    set /a REMAINING=!CALIB_TOTAL!-!CALIB_ELAPSED!
    echo Calibrating smartwatch - !REMAINING!s remaining, keep watch on your wrist...
) else (
    echo Calibrating smartwatch - finalising baseline, almost done...
)
if !CALIB_ELAPSED! lss !CALIB_MAX! goto CALIB_LOOP
echo [ILGC-WARN] Smartwatch calibration timed out - continuing without HRV features.

:CALIB_DONE

:: ════════════════════════════════════════════════════════════
:: STEP 8 — api_server
:: ════════════════════════════════════════════════════════════
echo [ILGC] Starting api_server.py...
start "ILGC api_server" /min cmd /c ""%PYTHON%" "%WIN_DIR%\api_server.py" >> "%SERVICE_LOG_DIR%\api_server.log" 2>&1"

set /a API_WAIT=0
:WAIT_API
curl -s http://localhost:5000/api/health >nul 2>&1
if not errorlevel 1 (
    echo [ILGC-OK] API server ready after !API_WAIT!s
    goto API_READY
)
timeout /t 1 /nobreak >nul
set /a API_WAIT+=1
if !API_WAIT! geq 30 (
    echo [ILGC-ERROR] API server did not start within 30s
    exit /b 1
)
goto WAIT_API
:API_READY

:: ════════════════════════════════════════════════════════════
:: STEP 9 — Remaining services
:: ════════════════════════════════════════════════════════════
echo [ILGC] Starting client.py...
start "ILGC client" /min cmd /c ""%PYTHON%" "%SRC_DIR%\client.py" >> "%SERVICE_LOG_DIR%\client.log" 2>&1"
timeout /t 3 /nobreak >nul

echo [ILGC] Starting collate_data.py...
start "ILGC collate_data" /min cmd /c ""%PYTHON%" "%SRC_DIR%\collate_data.py" >> "%SERVICE_LOG_DIR%\collate_data.log" 2>&1"
timeout /t 1 /nobreak >nul

if exist "%UTILS_DIR%\run_activity.py" (
    echo [ILGC] Starting run_activity.py...
    start "ILGC run_activity" /min cmd /c ""%PYTHON%" "%UTILS_DIR%\run_activity.py" >> "%SERVICE_LOG_DIR%\run_activity.log" 2>&1"
    timeout /t 1 /nobreak >nul
)

echo [ILGC] Starting frontend (Vite)...
start "ILGC frontend" /min cmd /c "cd /d "%FRONTEND_DIR%" && npm run dev >> "%SERVICE_LOG_DIR%\frontend.log" 2>&1"

set /a FE_WAIT=0
:WAIT_FE
curl -s http://localhost:8080 >nul 2>&1
if not errorlevel 1 (
    echo [ILGC-OK] Frontend ready
    goto FE_READY
)
timeout /t 1 /nobreak >nul
set /a FE_WAIT+=1
if !FE_WAIT! geq 30 goto FE_READY
goto WAIT_FE
:FE_READY

:: ════════════════════════════════════════════════════════════
:: STEP 10 — Signal Electron (main.js watches this string)
:: ════════════════════════════════════════════════════════════
echo All services running

echo.
echo API server    -^> http://localhost:5000
echo Frontend      -^> http://localhost:8080
echo ActivityWatch -^> http://localhost:5600
echo Data folder   -^> %APP_DATA_DIR%
echo Service logs  -^> %SERVICE_LOG_DIR%
echo.

:KEEPALIVE
timeout /t 10 /nobreak >nul
goto KEEPALIVE

:: ─────────────────────────────────────────────────────────────
:RefreshPath
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USER_PATH=%%b"
for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "SYS_PATH=%%b"
set "PATH=%SYS_PATH%;%USER_PATH%"
exit /b 0
