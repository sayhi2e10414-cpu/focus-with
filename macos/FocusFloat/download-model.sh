#!/usr/bin/env bash
set -euo pipefail

SOURCE="$(cd "$(dirname "$0")" && pwd)"
MODEL_DIR="$SOURCE/Models"
MODEL="$MODEL_DIR/YOLOv3FP16.mlmodel"
MODEL_URL="https://ml-assets.apple.com/coreml/models/Image/ObjectDetection/YOLOv3/YOLOv3FP16.mlmodel"
MODEL_SHA256="276afae53da362e25ad21c827f8a929a8512254b1343433d970e725a0de57d8f"

mkdir -p "$MODEL_DIR"
DOWNLOAD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/focusfloat-model.XXXXXX")"
trap 'rm -rf "$DOWNLOAD_DIR"' EXIT
DOWNLOAD="$DOWNLOAD_DIR/YOLOv3FP16.mlmodel"

curl --fail --location --progress-bar "$MODEL_URL" --output "$DOWNLOAD"
ACTUAL_MODEL_SHA256="$(LC_ALL=C LANG=C shasum -a 256 "$DOWNLOAD" | awk '{print $1}')"
if [[ "$ACTUAL_MODEL_SHA256" != "$MODEL_SHA256" ]]; then
  echo "Downloaded YOLOv3FP16 model checksum did not match." >&2
  exit 1
fi
mv "$DOWNLOAD" "$MODEL"
echo "$MODEL"
