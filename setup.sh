#!/bin/bash

# Resolve script directory
SCRIPT_DIR="$(cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_FOLDER="Bookah_Linux"
APP_BINARY="Bookah_Linux"
APP_BINARY_PATH="$SCRIPT_DIR/$APP_FOLDER/$APP_BINARY"
RUN_SCRIPT_PATH="$SCRIPT_DIR/run.sh"

# Dependencies
QT_LIBS="libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xinerama0"
WEB_LIBS="libnss3 libxcomposite1 libxcursor1 libasound2"
REQUIRED_PACKAGES="$QT_LIBS $WEB_LIBS"

echo "=== Bookah Setup ==="

# Check system dependencies
echo "Checking system dependencies..."
MISSING_PACKAGES=""
for pkg in $REQUIRED_PACKAGES; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
        MISSING_PACKAGES="$MISSING_PACKAGES $pkg"
    fi
done

if [ -n "$MISSING_PACKAGES" ]; then
    echo "Missing libraries found: $MISSING_PACKAGES"
    echo "Requesting sudo permissions to install them..."
    
    if sudo apt-get update && sudo apt-get install -y $MISSING_PACKAGES; then
        echo "Dependencies installed successfully."
    else
        echo "Error: Failed to install dependencies. Please check your internet connection."
        exit 1
    fi
else
    echo "All system dependencies are already installed."
fi

# Set execution permissions
if [ -f "$APP_BINARY_PATH" ]; then
    echo "Setting execution permissions..."
    chmod +x "$APP_BINARY_PATH"
    
    if [ -f "$RUN_SCRIPT_PATH" ]; then
        chmod +x "$RUN_SCRIPT_PATH"
    fi
    
    echo "Setup complete. You can now use run.sh to launch the application."
else
    echo "Error: Could not find application binary at: $APP_BINARY_PATH"
    exit 1
fi