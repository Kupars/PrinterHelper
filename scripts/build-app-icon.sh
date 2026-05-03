#!/bin/sh
set -eu

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ASSET_SVG="$PROJECT_ROOT/assets/app-icon.svg"
ICONSET_DIR="$PROJECT_ROOT/.runtime/app.iconset"
PNG_1024="$PROJECT_ROOT/.runtime/app-icon-1024.png"
ICNS_PATH="$PROJECT_ROOT/.runtime/双面打印助手.icns"

mkdir -p "$PROJECT_ROOT/.runtime"
rm -rf "$ICONSET_DIR"
/bin/rm -f "$PNG_1024" "$ICNS_PATH" "$PROJECT_ROOT/.runtime/$(basename "$ASSET_SVG").png"
mkdir -p "$ICONSET_DIR"

/usr/bin/qlmanage -t -s 1024 -o "$PROJECT_ROOT/.runtime" "$ASSET_SVG" >/dev/null 2>&1

if [ ! -f "$PNG_1024" ]; then
  THUMBNAIL_PATH="$PROJECT_ROOT/.runtime/$(basename "$ASSET_SVG").png"
  if [ -f "$THUMBNAIL_PATH" ]; then
    mv "$THUMBNAIL_PATH" "$PNG_1024"
  fi
fi

if [ ! -f "$PNG_1024" ]; then
  echo "failed to render icon PNG" >&2
  exit 1
fi

cp "$PNG_1024" "$ICONSET_DIR/icon_512x512@2x.png"
/usr/bin/sips -z 16 16 "$PNG_1024" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
/usr/bin/sips -z 32 32 "$PNG_1024" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
/usr/bin/sips -z 32 32 "$PNG_1024" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
/usr/bin/sips -z 64 64 "$PNG_1024" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
/usr/bin/sips -z 128 128 "$PNG_1024" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
/usr/bin/sips -z 256 256 "$PNG_1024" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
/usr/bin/sips -z 256 256 "$PNG_1024" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
/usr/bin/sips -z 512 512 "$PNG_1024" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
/usr/bin/sips -z 512 512 "$PNG_1024" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
/usr/bin/iconutil -c icns "$ICONSET_DIR" -o "$ICNS_PATH"

echo "$ICNS_PATH"
