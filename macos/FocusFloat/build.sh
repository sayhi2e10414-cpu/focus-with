#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SOURCE="$ROOT/macos/FocusFloat"
APP="$ROOT/generated/FocusFloat.app"
MACOS="$APP/Contents/MacOS"
RESOURCES="$APP/Contents/Resources"
MODEL="$SOURCE/Models/YOLOv3FP16.mlmodel"
MODEL_SHA256="276afae53da362e25ad21c827f8a929a8512254b1343433d970e725a0de57d8f"

if ! command -v clang >/dev/null 2>&1; then
  echo "FocusFloat needs Apple Command Line Tools. Run: xcode-select --install" >&2
  exit 1
fi

if [[ ! -f "$MODEL" ]]; then
  "$SOURCE/download-model.sh"
fi
ACTUAL_MODEL_SHA256="$(LC_ALL=C LANG=C shasum -a 256 "$MODEL" | awk '{print $1}')"
if [[ "$ACTUAL_MODEL_SHA256" != "$MODEL_SHA256" ]]; then
  echo "Unexpected YOLOv3FP16 model checksum." >&2
  exit 1
fi

rm -rf "$APP"
mkdir -p "$MACOS" "$RESOURCES"
cp "$SOURCE/Info.plist" "$APP/Contents/Info.plist"
cp "$MODEL" "$RESOURCES/YOLOv3FP16.mlmodel"
clang -fobjc-arc -O2 -mmacosx-version-min=13.0 \
  -framework Cocoa -framework Security -framework AVFoundation -framework CoreML \
  -framework CoreMedia -framework CoreVideo -framework QuartzCore -framework Vision \
  "$SOURCE/main.m" "$SOURCE/AppDelegate.m" "$SOURCE/FocusAPIClient.m" \
  "$SOURCE/FocusCameraController.m" "$SOURCE/FocusPhonePresenceTracker.m" \
  "$SOURCE/FocusPanelController.m" \
  -o "$MACOS/FocusFloat"
codesign --force --deep --sign - "$APP" >/dev/null
echo "$APP"
