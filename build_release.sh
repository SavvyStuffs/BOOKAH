#!/bin/bash

# ==============================================================================
# BOOKAH LINUX RELEASE BUILDER
# ==============================================================================

# --- CONFIGURATION ------------------------------------------------------------
WINDOWS_PROJECT_PATH="/mnt/c/Users/coura/OneDrive/Documents/Programs/BOOKAH"
BUILD_LAB="$HOME/Bookah_Build_Lab"
SPEC_FILE="bookah_linux.spec"
INSTALLER_SCRIPT="install_and_run.sh"
OUTPUT_ZIP="Bookah_Linux_$(date +%Y-%m-%d).zip"

# Smart Delivery Path: Auto-detects if Windows is using the OneDrive Desktop folder
if [ -d "/mnt/c/Users/coura/OneDrive/Desktop" ]; then
    DELIVERY_PATH="/mnt/c/Users/coura/OneDrive/Desktop"
else
    DELIVERY_PATH="/mnt/c/Users/coura/Desktop"
fi

# --- FUNCTIONS ----------------------------------------------------------------
log() {
    echo -e "\033[1;32m[BUILDER]\033[0m $1"
}

error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
    exit 1
}

# --- EXECUTION ----------------------------------------------------------------

# 1. Safety Check
if [ ! -d "$WINDOWS_PROJECT_PATH" ]; then
    error "Source folder not found at: $WINDOWS_PROJECT_PATH"
fi

log "Step 1/5: Syncing Source to Native Linux Lab..."
# Clean previous artifacts
rm -rf "$BUILD_LAB"
mkdir -p "$BUILD_LAB"

# Sync code (Excluding Windows-specific venv/git/build artifacts)
rsync -a --exclude='.git' --exclude='__pycache__' --exclude='venv' \
      --exclude='build' --exclude='dist' --exclude='.idea' \
      "$WINDOWS_PROJECT_PATH/" "$BUILD_LAB/" || error "Rsync failed"

log "Step 2/5: Compiling Binary (PyInstaller)..."
cd "$BUILD_LAB" || error "Could not enter build lab"

# Build using the Linux spec file
python3 -m PyInstaller --clean "$SPEC_FILE" || error "PyInstaller Build Failed"

# Verify binary existence
if [ ! -f "dist/Bookah_Linux/Bookah_Linux" ]; then
    error "Build finished, but binary not found. Check spec file output."
fi

log "Step 3/5: Injecting Launcher Script..."
# Ensure the installer script is copied from source and made executable
if [ -f "$INSTALLER_SCRIPT" ]; then
    cp "$INSTALLER_SCRIPT" "dist/Bookah_Linux/"
    chmod +x "dist/Bookah_Linux/$INSTALLER_SCRIPT"
else
    error "install_and_run.sh not found in source! Cannot package release."
fi

log "Step 4/5: Packaging for Distribution..."
cd dist
zip -r -q "$OUTPUT_ZIP" Bookah_Linux || error "Zipping failed"

log "Step 5/5: Delivery..."
mv "$OUTPUT_ZIP" "$DELIVERY_PATH/" || error "Failed to move ZIP to Desktop"

echo ""
echo "=================================================================="
echo "   SUCCESS! Release ready at:"
echo "   $DELIVERY_PATH/$OUTPUT_ZIP"
echo "=================================================================="
