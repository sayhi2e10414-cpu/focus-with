#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILT="$($ROOT/macos/FocusFloat/build.sh)"
DEST="$HOME/Applications/FocusFloat.app"
mkdir -p "$HOME/Applications"
if [[ -e "$DEST" ]]; then mv "$DEST" "$HOME/Applications/FocusFloat.backup-$(date +%Y%m%d-%H%M%S).app"; fi
ditto "$BUILT" "$DEST"
open "$DEST"
echo "$DEST"
