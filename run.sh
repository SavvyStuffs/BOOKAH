#!/bin/bash

# Resolve script directory
SCRIPT_DIR="$(cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_FOLDER="Bookah_Linux"
APP_BINARY="Bookah_Linux"
APP_PATH="$SCRIPT_DIR/$APP_FOLDER/$APP_BINARY"

# Environment Configuration
export QT_QPA_PLATFORM=xcb

# Launch Application
if [ -f "$APP_PATH" ]; then
    "$APP_PATH" "$@" > /dev/null 2>&1 & 
else
    echo "Error: Application binary not found at $APP_PATH"
    echo "Please run setup.sh first."
    exit 1
fi