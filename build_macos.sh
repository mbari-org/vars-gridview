#!/bin/bash

# Check that OS is macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "This script is only for macOS"
    exit 1
fi

# Check that Xcode is installed
if ! command -v xcodebuild &> /dev/null; then
    echo "Xcode is not installed"
    exit 1
fi

# Check that Xcode command line tools are installed
if ! command -v xcode-select &> /dev/null; then
    echo "Xcode command line tools are not installed"
    exit 1
fi

# Parse arguments
if [ $# -ne 2 ]; then
    echo "Usage: $0 <apple_id> <apple_id_password>"
    exit 1
fi

export MAC_CODE_SIGNER="Developer ID Application: Monterey Bay Aquarium Research Institute (9TN7A342V4)"
export TEAM_ID="9TN7A342V4"
export APPLE_ID=$1
export APPLE_ID_PASSWORD=$2

# Build and sign
pyinstaller -y run.spec

# Zip
cd dist
ditto -c -k --keepParent "VARS GridView.app" "VARS GridView.zip"

# Notarize
xcrun notarytool submit "VARS GridView.zip" \
    --wait \
    --team-id "$TEAM_ID" \
    --apple-id "$APPLE_ID" \
    --password "$APPLE_ID_PASSWORD"

# Exit if notarization failed
if [ $? -ne 0 ]; then
    echo "Notarization failed"
    exit 1
fi

# Staple
xcrun stapler staple "VARS GridView.app"

rm "VARS GridView.zip"

# Repack for distribution
ditto -c -k --keepParent "VARS GridView.app" "VARS GridView.zip"
