@echo off
setlocal EnableDelayedExpansion

:: ─────────────────────────────────────────────────────────────
:: ILGC Windows Launcher
:: Installs Python, Node.js, ActivityWatch, sets up venv,
:: then starts all services in one script.
:: Close this window or press Ctrl+C to stop everything.
:: ─────────────────────────────────────────────────────────────

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "WIN_DIR=%SCRIPT_DIR%\windows"
set "SRC_DIR=%WIN_DIR%\src"
set "UTILS_DIR=%SCRIPT_DIR%\utils"
set "FRONTEND_DIR=%WIN_DIR%\frontend"
set "VENV=%WIN_DIR%\.ilgc"
set "PYTHON=%VENV%\Scripts\python.exe"

echo.
echo ══════════════════════════════════════════════════════
echo    ILGC Workplace ^& Distraction Monitor — Windows
echo ══════════════════════════════════════════════════════
echo.

:: ─────────────────────────────────────────────────────────────
:: STEP 1 — Check for Python
:: ─────────────────────────────────────────────────────────────
echo [ILGC] Checking for Python 3...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ILGC] Python not found. Attempting to install via winget...
    winget install -e --id Python.Python.3.12 --silent
    if errorlevel 1 (
        echo [ERROR] Could not install Python automatically.
        echo         Please install Python 3.12 from https://www.python.org/downloads/
        echo         Make sure to check "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
    :: Refresh PATH
    call :RefreshPath
    python --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python still not found after install. Please restart and try again.
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [ILGC] Found %%v

:: ─────────────────────────────────────────────────────────────
:: STEP 2 — Check for Node.js / npm
:: ─────────────────────────────────────────────────────────────
echo [ILGC] Checking for Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [ILGC] Node.js not found. Attempting to install via winget...
    winget install -e --id OpenJS.NodeJS --silent
    if errorlevel 1 (
        echo [ERROR] Could not install Node.js automatically.
        echo         Please install Node.js from https://nodejs.org/
        pause
        exit /b 1
    )
    call :RefreshPath
    node --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Node.js still not found after install. Please restart and try again.
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo [ILGC] Node.js %%v found.

:: ─────────────────────────────────────────────────────────────
:: STEP 3 — ActivityWatch (via utils/windows.bat)
:: ─────────────────────────────────────────────────────────────
set "AW_SCRIPT=%UTILS_DIR%\windows.bat"
if not exist "%AW_SCRIPT%" (
    echo [ERROR] utils\windows.bat not found at %AW_SCRIPT%
    pause
    exit /b 1
)

echo [ILGC] Launching ActivityWatch via utils\windows.bat...
start "ActivityWatch" /min cmd /c ""%AW_SCRIPT%""
echo [ILGC] ActivityWatch launching (background)...
:: Give AW time to start before continuing
timeout /t 5 /nobreak >nul

:: ─────────────────────────────────────────────────────────────
:: STEP 4 — Check windows/ directory
:: ─────────────────────────────────────────────────────────────
if not exist "%WIN_DIR%" (
    echo [ERROR] Could not find 'windows\' directory at: %WIN_DIR%
    echo         Make sure you run this script from the project root.
    pause
    exit /b 1
)

:: ─────────────────────────────────────────────────────────────
:: STEP 5 — Virtual environment (windows\.ilgc)
:: ─────────────────────────────────────────────────────────────
if not exist "%PYTHON%" (
    echo [ILGC] Creating .ilgc virtual environment...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [ILGC] Virtual environment created.
) else (
    echo [ILGC] Virtual environment found.
)

:: ─────────────────────────────────────────────────────────────
:: STEP 6 — Python dependencies (windows\requirements.txt)
:: ─────────────────────────────────────────────────────────────
set "REQUIREMENTS=%WIN_DIR%\requirements.txt"
if not exist "%REQUIREMENTS%" (
    echo [ERROR] requirements.txt not found at %REQUIREMENTS%
    pause
    exit /b 1
)

"%PYTHON%" -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [ILGC] Installing Python dependencies...
    "%PYTHON%" -m pip install --upgrade pip --quiet
    "%PYTHON%" -m pip install -r "%REQUIREMENTS%" --quiet
    if errorlevel 1 (
        echo [ERROR] Failed to install Python dependencies.
        pause
        exit /b 1
    )
    echo [ILGC] Python dependencies installed.
) else (
    echo [ILGC] Python dependencies already installed.
)

:: ─────────────────────────────────────────────────────────────
:: STEP 7 — Frontend dependencies
:: ─────────────────────────────────────────────────────────────
if not exist "%FRONTEND_DIR%\node_modules" (
    echo [ILGC] Installing frontend dependencies (first run)...
    pushd "%FRONTEND_DIR%"
    call npm install --silent
    popd
    echo [ILGC] Frontend dependencies installed.
) else (
    echo [ILGC] Frontend dependencies already installed.
)

:: ─────────────────────────────────────────────────────────────
:: STEP 8 — Start Python backend services
:: ─────────────────────────────────────────────────────────────

:: api_server.py — windows\
echo [ILGC] Starting api_server.py...
pushd "%WIN_DIR%"
start "ILGC api_server" /min cmd /c ""%PYTHON%" api_server.py & pause"
popd
echo [ILGC] api_server.py started.
timeout /t 1 /nobreak >nul

:: watch.py — windows\src\
echo [ILGC] Starting watch.py...
pushd "%SRC_DIR%"
start "ILGC watch" /min cmd /c ""%PYTHON%" watch.py & pause"
popd
echo [ILGC] watch.py started.
timeout /t 1 /nobreak >nul

:: client.py — windows\src\
echo [ILGC] Starting client.py...
pushd "%SRC_DIR%"
start "ILGC client" /min cmd /c ""%PYTHON%" client.py & pause"
popd
echo [ILGC] client.py started.
timeout /t 1 /nobreak >nul

:: collate_data.py — windows\src\
echo [ILGC] Starting collate_data.py...
pushd "%SRC_DIR%"
start "ILGC collate_data" /min cmd /c ""%PYTHON%" collate_data.py & pause"
popd
echo [ILGC] collate_data.py started.
timeout /t 1 /nobreak >nul

:: run_activity.py — run from windows\src\ so activity.json
:: lands at windows\src\activityTracker\activity.json
if exist "%UTILS_DIR%\run_activity.py" (
    echo [ILGC] Starting run_activity.py...
    pushd "%SRC_DIR%"
    start "ILGC run_activity" /min cmd /c ""%PYTHON%" "%UTILS_DIR%\run_activity.py" & pause"
    popd
    echo [ILGC] run_activity.py started.
    timeout /t 1 /nobreak >nul
) else (
    echo [ILGC] run_activity.py not found at %UTILS_DIR% — skipping.
)

:: ─────────────────────────────────────────────────────────────
:: STEP 9 — Start frontend (Vite)
:: ─────────────────────────────────────────────────────────────
echo [ILGC] Starting frontend (Vite)...
pushd "%FRONTEND_DIR%"
start "ILGC frontend" /min cmd /c "npm run dev & pause"
popd
echo [ILGC] Frontend started.

:: ─────────────────────────────────────────────────────────────
:: Done — wait and keep alive so closing this window
:: signals the user to stop services manually.
:: ─────────────────────────────────────────────────────────────
echo.
echo ══════════════════════════════════════════════════════
echo  [ILGC] All services running!
echo.
echo    API server     -^> http://localhost:5000
echo    Frontend       -^> http://localhost:8080
echo    ActivityWatch  -^> http://localhost:5600
echo.
echo  Close this window or press Ctrl+C to stop.
echo  NOTE: Background service windows must be closed
echo        manually, or run stop_windows.bat to stop all.
echo ══════════════════════════════════════════════════════
echo.

:: Keep this window alive
:KEEPALIVE
timeout /t 10 /nobreak >nul
goto KEEPALIVE

:: ─────────────────────────────────────────────────────────────
:: Helper: refresh PATH from registry (so newly installed
:: tools are available without reopening the terminal)
:: ─────────────────────────────────────────────────────────────
:RefreshPath
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USER_PATH=%%b"
for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "SYS_PATH=%%b"
set "PATH=%SYS_PATH%;%USER_PATH%"
exit /b 0