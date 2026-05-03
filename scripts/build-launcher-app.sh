#!/bin/sh
set -eu

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_BUNDLE="$PROJECT_ROOT/双面打印助手.app"
CONTENTS_DIR="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
PAYLOAD_DIR="$RESOURCES_DIR/AppPayload"
PAYLOAD_WEBAPP_DIR="$PAYLOAD_DIR/webapp"
PAYLOAD_SCRIPTS_DIR="$PAYLOAD_DIR/scripts"
ICON_SOURCE="$("$PROJECT_ROOT/scripts/build-app-icon.sh")"

/bin/rm -rf "$APP_BUNDLE"
/bin/mkdir -p "$MACOS_DIR" "$RESOURCES_DIR/Scripts" "$PAYLOAD_WEBAPP_DIR" "$PAYLOAD_SCRIPTS_DIR"

/bin/cp "$PROJECT_ROOT/scripts/app-main.sh" "$MACOS_DIR/双面打印助手"
/bin/chmod +x "$MACOS_DIR/双面打印助手"

/bin/cp "$ICON_SOURCE" "$RESOURCES_DIR/AppIcon.icns"

/bin/cp "$PROJECT_ROOT/scripts/app-bundled-launcher.sh" "$RESOURCES_DIR/Scripts/launcher.sh"
/bin/chmod +x "$RESOURCES_DIR/Scripts/launcher.sh"

/bin/cp "$PROJECT_ROOT/webapp/server.py" "$PAYLOAD_WEBAPP_DIR/server.py"
/bin/cp "$PROJECT_ROOT/webapp/index.html" "$PAYLOAD_WEBAPP_DIR/index.html"
/bin/cp "$PROJECT_ROOT/scripts/webapp-control.sh" "$PAYLOAD_SCRIPTS_DIR/webapp-control.sh"
/bin/cp "$PROJECT_ROOT/scripts/run-manual-duplex-web.sh" "$PAYLOAD_SCRIPTS_DIR/run-manual-duplex-web.sh"
/bin/cp "$PROJECT_ROOT/scripts/folder_to_manual_duplex.py" "$PAYLOAD_SCRIPTS_DIR/folder_to_manual_duplex.py"
/bin/cp "$PROJECT_ROOT/scripts/manual_duplex_pdf.py" "$PAYLOAD_SCRIPTS_DIR/manual_duplex_pdf.py"
/bin/chmod +x "$PAYLOAD_SCRIPTS_DIR/webapp-control.sh" "$PAYLOAD_SCRIPTS_DIR/run-manual-duplex-web.sh"

cat >"$CONTENTS_DIR/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>zh_CN</string>
  <key>CFBundleExecutable</key>
  <string>双面打印助手</string>
  <key>CFBundleIdentifier</key>
  <string>com.openai.manualduplex.app</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIconName</key>
  <string>AppIcon</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>双面打印助手</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
</dict>
</plist>
EOF

printf 'APPL????' >"$CONTENTS_DIR/PkgInfo"
/usr/bin/touch "$APP_BUNDLE"

LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
if [ -x "$LSREGISTER" ]; then
  "$LSREGISTER" -f "$APP_BUNDLE" >/dev/null 2>&1 || true
fi
