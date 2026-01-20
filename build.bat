@echo off
REM ============================================================================
REM ILGC Workplace Monitor - Windows Build Script
REM ============================================================================
REM This script builds the ILGC application for Windows
REM
REM Prerequisites:
REM - Python 3.8+ installed and in PATH
REM - Node.js 18+ installed and in PATH
REM - npm installed
REM
REM Usage:
REM   build.bat
REM ============================================================================

setlocal EnableDelayedExpansion

REM Colors (Windows 10+)
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

REM Configuration
set "PROJECT_ROOT=%~dp0"
set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "WINDOWS_DIR=%PROJECT_ROOT%\windows"
set "VENV_DIR=%PROJECT_ROOT%\.build_venv"
set "DIST_DIR=%PROJECT_ROOT%\dist"
set "BUILD_DIR=%PROJECT_ROOT%\build"
set "APP_NAME=ILGC-Workplace"

echo.
echo %BLUE%========================================================================%NC%
echo %BLUE%       ILGC Workplace Monitor - Windows Build Script%NC%
echo %BLUE%========================================================================%NC%
echo.

REM ============================================================================
REM Step 1: Check Prerequisites
REM ============================================================================

echo %BLUE%[INFO]%NC% Checking prerequisites...

REM Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[ERROR]%NC% Python is not installed or not in PATH
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo %BLUE%[INFO]%NC% Python version: %PYTHON_VERSION%

REM Check Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[ERROR]%NC% Node.js is not installed or not in PATH
    exit /b 1
)

for /f "tokens=*" %%v in ('node --version') do set NODE_VERSION=%%v
echo %BLUE%[INFO]%NC% Node.js version: %NODE_VERSION%

REM Check npm
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[ERROR]%NC% npm is not installed or not in PATH
    exit /b 1
)

for /f "tokens=*" %%v in ('npm --version') do set NPM_VERSION=%%v
echo %BLUE%[INFO]%NC% npm version: %NPM_VERSION%

echo %GREEN%[SUCCESS]%NC% All prerequisites satisfied

REM ============================================================================
REM Step 2: Create Virtual Environment
REM ============================================================================

echo %BLUE%[INFO]%NC% Creating Python virtual environment...

REM Remove existing venv if exists
if exist "%VENV_DIR%" (
    echo %YELLOW%[WARNING]%NC% Removing existing virtual environment...
    rmdir /s /q "%VENV_DIR%"
)

python -m venv "%VENV_DIR%"
call "%VENV_DIR%\Scripts\activate.bat"

echo %GREEN%[SUCCESS]%NC% Virtual environment created and activated

REM ============================================================================
REM Step 3: Install Python Dependencies
REM ============================================================================

echo %BLUE%[INFO]%NC% Installing Python dependencies...

python -m pip install --upgrade pip
pip install -r "%WINDOWS_DIR%\requirements.txt"
pip install pyinstaller

echo %GREEN%[SUCCESS]%NC% Python dependencies installed

REM ============================================================================
REM Step 4: Build Frontend
REM ============================================================================

echo %BLUE%[INFO]%NC% Building frontend...

cd /d "%WINDOWS_DIR%\frontend"

echo %BLUE%[INFO]%NC% Installing frontend dependencies...
call npm install

echo %BLUE%[INFO]%NC% Building frontend for production...
call npm run build

REM Verify build
if not exist "%WINDOWS_DIR%\frontend\dist" (
    echo %RED%[ERROR]%NC% Frontend build failed - dist directory not found
    exit /b 1
)

echo %GREEN%[SUCCESS]%NC% Frontend built successfully

cd /d "%PROJECT_ROOT%"

REM ============================================================================
REM Step 5: Build Executable with PyInstaller
REM ============================================================================

echo %BLUE%[INFO]%NC% Building executable with PyInstaller...

REM Clean previous builds
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"

REM Run PyInstaller
pyinstaller ilgc_windows.spec --clean --noconfirm

REM Verify build
if not exist "%DIST_DIR%\%APP_NAME%.exe" (
    echo %RED%[ERROR]%NC% PyInstaller build failed - executable not found
    exit /b 1
)

echo %GREEN%[SUCCESS]%NC% Executable built successfully

REM ============================================================================
REM Step 6: Create Installer with Inno Setup
REM ============================================================================

echo %BLUE%[INFO]%NC% Creating installer...

REM Check if Inno Setup is installed
set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if defined ISCC (
    echo %BLUE%[INFO]%NC% Running Inno Setup...
    "%ISCC%" "%PROJECT_ROOT%\installer_windows.iss"
    
    if exist "%PROJECT_ROOT%\Output\ILGC-Setup-Windows.exe" (
        echo %GREEN%[SUCCESS]%NC% Installer created successfully
    ) else (
        echo %YELLOW%[WARNING]%NC% Installer creation may have failed
    )
) else (
    echo %YELLOW%[WARNING]%NC% Inno Setup not found. Skipping installer creation.
    echo %YELLOW%[WARNING]%NC% Install Inno Setup from: https://jrsoftware.org/isinfo.php
    echo %YELLOW%[WARNING]%NC% Standalone executable is available at: %DIST_DIR%\%APP_NAME%.exe
)

REM ============================================================================
REM Step 7: Cleanup
REM ============================================================================

echo %BLUE%[INFO]%NC% Cleaning up...

REM Deactivate virtual environment
call deactivate

echo %GREEN%[SUCCESS]%NC% Cleanup complete

REM ============================================================================
REM Done
REM ============================================================================

echo.
echo %GREEN%========================================================================%NC%
echo %GREEN%                        BUILD COMPLETE%NC%
echo %GREEN%========================================================================%NC%
echo.
echo Output files:
echo   - Executable: %DIST_DIR%\%APP_NAME%.exe

if exist "%PROJECT_ROOT%\Output\ILGC-Setup-Windows.exe" (
    echo   - Installer:  %PROJECT_ROOT%\Output\ILGC-Setup-Windows.exe
)

echo.
echo To run the application:
echo   1. Double-click %APP_NAME%.exe
echo   2. Grant camera permissions when prompted
echo   3. Application will open in your browser
echo.

pause
