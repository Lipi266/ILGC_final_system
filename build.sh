#!/bin/bash
# ============================================================================
# ILGC Workplace Monitor - macOS Build Script
# ============================================================================
# This script builds the ILGC application for macOS
#
# Prerequisites:
# - Python 3.8+ installed
# - Node.js 18+ installed
# - npm installed
# - Xcode Command Line Tools (xcode-select --install)
#
# Usage:
#   chmod +x build.sh
#   ./build.sh
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
MAC_DIR="$PROJECT_ROOT/mac"
VENV_DIR="$PROJECT_ROOT/.build_venv"
DIST_DIR="$PROJECT_ROOT/dist"
BUILD_DIR="$PROJECT_ROOT/build"
APP_NAME="ILGC-Workplace"

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║       ILGC Workplace Monitor - macOS Build Script             ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is not installed. Please install it first."
        exit 1
    fi
}

# ============================================================================
# Step 1: Check Prerequisites
# ============================================================================

log_info "Checking prerequisites..."

# Check Python
check_command python3
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
log_info "Python version: $PYTHON_VERSION"

# Verify Python 3.8+
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    log_error "Python 3.8 or higher is required. Found: $PYTHON_VERSION"
    exit 1
fi

# Check Node.js
check_command node
NODE_VERSION=$(node --version)
log_info "Node.js version: $NODE_VERSION"

# Check npm
check_command npm
NPM_VERSION=$(npm --version)
log_info "npm version: $NPM_VERSION"

log_success "All prerequisites satisfied"

# ============================================================================
# Step 2: Create Virtual Environment
# ============================================================================

log_info "Creating Python virtual environment..."

# Remove existing venv if exists
if [ -d "$VENV_DIR" ]; then
    log_warning "Removing existing virtual environment..."
    rm -rf "$VENV_DIR"
fi

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

log_success "Virtual environment created and activated"

# ============================================================================
# Step 3: Install Python Dependencies
# ============================================================================

log_info "Installing Python dependencies..."

pip install --upgrade pip
pip install -r "$MAC_DIR/requirements.txt"
pip install pyinstaller

# Verify critical packages
python -c "import flask; import cv2; import numpy; import bleak" 2>/dev/null || {
    log_error "Failed to import required packages"
    exit 1
}

log_success "Python dependencies installed"

# ============================================================================
# Step 4: Setup pylsl Library
# ============================================================================

log_info "Setting up pylsl library..."

PYLSL_LIB_SRC="$MAC_DIR/lib/pylsl"
PYLSL_SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])")/pylsl/lib

if [ -d "$PYLSL_LIB_SRC" ]; then
    mkdir -p "$PYLSL_SITE_PACKAGES"
    cp -r "$PYLSL_LIB_SRC/"* "$PYLSL_SITE_PACKAGES/" 2>/dev/null || true
    log_success "pylsl library files copied"
else
    log_warning "pylsl library source not found at $PYLSL_LIB_SRC"
fi

# ============================================================================
# Step 5: Build Frontend
# ============================================================================

log_info "Building frontend..."

cd "$MAC_DIR/frontend"

# Install dependencies
log_info "Installing frontend dependencies..."
npm install

# Build for production
log_info "Building frontend for production..."
npm run build

# Verify build
if [ ! -d "$MAC_DIR/frontend/dist" ]; then
    log_error "Frontend build failed - dist directory not found"
    exit 1
fi

log_success "Frontend built successfully"

cd "$PROJECT_ROOT"

# ============================================================================
# Step 6: Build Executable with PyInstaller
# ============================================================================

log_info "Building executable with PyInstaller..."

# Clean previous builds
rm -rf "$DIST_DIR" "$BUILD_DIR"

# Run PyInstaller
pyinstaller ilgc_macos.spec --clean --noconfirm

# Verify build
if [ ! -d "$DIST_DIR/$APP_NAME.app" ]; then
    log_error "PyInstaller build failed - .app bundle not found"
    exit 1
fi

log_success "Executable built successfully"

# ============================================================================
# Step 7: Create DMG
# ============================================================================

log_info "Creating DMG installer..."

DMG_NAME="${APP_NAME}.dmg"
DMG_PATH="$DIST_DIR/$DMG_NAME"
DMG_STAGING="$DIST_DIR/dmg_staging"

# Remove existing DMG and staging
rm -f "$DMG_PATH"
rm -rf "$DMG_STAGING"

# Create staging directory with app and Applications symlink
mkdir -p "$DMG_STAGING"
cp -R "$DIST_DIR/$APP_NAME.app" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"

# Check if create-dmg is available (install it if not)
if ! command -v create-dmg &> /dev/null; then
    log_info "Installing create-dmg..."
    brew install create-dmg || true
fi

if command -v create-dmg &> /dev/null; then
    create-dmg \
        --volname "$APP_NAME" \
        --window-pos 200 120 \
        --window-size 600 450 \
        --icon-size 100 \
        --icon "$APP_NAME.app" 150 200 \
        --hide-extension "$APP_NAME.app" \
        --app-drop-link 450 200 \
        --no-internet-enable \
        "$DMG_PATH" \
        "$DMG_STAGING" || {
            log_warning "create-dmg failed, using hdiutil..."
            hdiutil create -volname "$APP_NAME" -srcfolder "$DMG_STAGING" -ov -format UDZO "$DMG_PATH"
        }
else
    # Use hdiutil as fallback (still has Applications link from staging)
    log_warning "create-dmg not found, using hdiutil..."
    hdiutil create -volname "$APP_NAME" -srcfolder "$DMG_STAGING" -ov -format UDZO "$DMG_PATH"
fi

# Cleanup staging
rm -rf "$DMG_STAGING"

log_success "DMG created: $DMG_PATH"

# ============================================================================
# Step 8: Cleanup
# ============================================================================

log_info "Cleaning up..."

# Deactivate virtual environment
deactivate

# Optionally remove build artifacts (keep for debugging)
# rm -rf "$BUILD_DIR"

log_success "Cleanup complete"

# ============================================================================
# Done
# ============================================================================

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                     BUILD COMPLETE                            ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Output files:"
echo "  - Application: $DIST_DIR/$APP_NAME.app"
echo "  - Installer:   $DMG_PATH"
echo ""
echo "To install:"
echo "  1. Open $DMG_NAME"
echo "  2. Drag $APP_NAME to Applications"
echo "  3. Launch from Applications folder"
echo ""
