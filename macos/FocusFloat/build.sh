#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SOURCE="$ROOT/macos/FocusFloat"
APP="$ROOT/generated/FocusFloat.app"
MACOS="$APP/Contents/MacOS"

if ! command -v clang >/dev/null 2>&1; then
  echo "FocusFloat needs Apple Command Line Tools. Run: xcode-select --install" >&2
  exit 1
fi

rm -rf "$APP"
mkdir -p "$MACOS"
cp "$SOURCE/Info.plist" "$APP/Contents/Info.plist"
clang -fobjc-arc -O2 -mmacosx-version-min=13.0 -framework Cocoa -framework Security \
  "$SOURCE/main.m" "$SOURCE/AppDelegate.m" "$SOURCE/FocusAPIClient.m" "$SOURCE/FocusPanelController.m" \
  -o "$MACOS/FocusFloat"
codesign --force --deep --sign - "$APP" >/dev/null
echo "$APP"
