#!/usr/bin/env bash
set -euo pipefail

SOURCE="$(cd "$(dirname "$0")" && pwd)"
MODEL="$SOURCE/Models/YOLOv3FP16.mlmodel"
API_TEST="${TMPDIR:-/tmp}/FocusWithAPIClientTests"
TRACKER_TEST="${TMPDIR:-/tmp}/FocusWithPhonePresenceTrackerTests"
VISION_TEST="${TMPDIR:-/tmp}/FocusWithVisionModelTests"

if [[ ! -f "$MODEL" ]]; then
  "$SOURCE/download-model.sh"
fi

clang -fobjc-arc -O0 -mmacosx-version-min=13.0 -framework Cocoa \
  "$SOURCE/FocusAPIClient.m" "$SOURCE/FocusAPIClientTests.m" -o "$API_TEST"
"$API_TEST"

clang -fobjc-arc -O0 -mmacosx-version-min=13.0 -framework Foundation \
  "$SOURCE/FocusPhonePresenceTracker.m" "$SOURCE/FocusPhonePresenceTrackerTests.m" -o "$TRACKER_TEST"
"$TRACKER_TEST"

clang -fobjc-arc -O0 -mmacosx-version-min=13.0 -framework CoreML -framework Foundation -framework Vision \
  "$SOURCE/FocusVisionModelTests.m" -o "$VISION_TEST"
"$VISION_TEST" "$MODEL"

"$SOURCE/build.sh" >/dev/null
APP="$SOURCE/../../generated/FocusFloat.app"
codesign --verify --deep --strict "$APP"
plutil -lint "$APP/Contents/Info.plist"
plutil -extract NSCameraUsageDescription raw "$APP/Contents/Info.plist" >/dev/null
test -f "$APP/Contents/Resources/YOLOv3FP16.mlmodel"
