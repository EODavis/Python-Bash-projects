#!/bin/bash
# build_exe.sh — Build Email-to-Task Converter as a standalone .exe
# Requires: pip install pyinstaller
#
# Usage:
#   bash build_exe.sh
#
# Output:
#   dist/EmailTaskConverter.exe  (Windows)
#   dist/EmailTaskConverter      (Linux/macOS)

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENTRY="$PROJECT_DIR/src/gui.py"
DIST="$PROJECT_DIR/dist"
BUILD="$PROJECT_DIR/build_tmp"
NAME="EmailTaskConverter"

echo ""
echo "  🔨 Building $NAME..."
echo "  Entry : $ENTRY"
echo "  Output: $DIST/"
echo ""

pyinstaller \
  --onefile \
  --noconsole \
  --name "$NAME" \
  --distpath "$DIST" \
  --workpath "$BUILD" \
  --specpath "$BUILD" \
  --add-data "templates:templates" \
  "$ENTRY"

echo ""
echo "  ✅ Build complete → $DIST/$NAME"
echo ""

# Cleanup build artifacts (keep dist/)
rm -rf "$BUILD"
