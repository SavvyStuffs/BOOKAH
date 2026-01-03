#!/bin/bash

# Resolve script directory to handle symlinks and execution from other paths
SCRIPT_DIR="$(cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_FOLDER="Bookah_Linux"
APP_BINARY="Bookah_Linux"
APP_PATH="$SCRIPT_DIR/$APP_FOLDER/$APP_BINARY"

# Core Qt6 and WebEngine runtime dependencies
QT_LIBS="libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xinerama0"
WEB_LIBS="libnss3 libxcomposite1 libxcursor1 libasound2"
REQUIRED_PACKAGES="$QT_LIBS $WEB_LIBS"

check_dependencies() {
    MISSING_PACKAGES=""
    for pkg in $REQUIRED_PACKAGES; do
        if ! dpkg -s "$pkg" >/dev/null 2>&1; then
            MISSING_PACKAGES="$MISSING_PACKAGES $pkg"
        fi
    done
}

# Verify and install dependencies if needed
check_dependencies
if [ -n "$MISSING_PACKAGES" ]; then
    echo "[$APP_BINARY] Installing missing system libraries: $MISSING_PACKAGES"
    
    # Quiet install, only surfacing errors
    if sudo apt-get update -qq && sudo apt-get install -y -qq $MISSING_PACKAGES; then
        echo "[$APP_BINARY] Dependencies verified."
    else
        echo "Error: Failed to install dependencies. Please check network connection."
        exit 1
    fi
fi

# Force XCB platform to ensure compatibility across DEs (Gnome/KDE/etc)
export QT_QPA_PLATFORM=xcb

if [ -f "$APP_PATH" ]; then
    chmod -R 755 "$SCRIPT_DIR/Bookah_Linux"
    "$APP_PATH" "$@" &
else
    echo "Error: Executable not found at $APP_PATH"
    exit 1
fi