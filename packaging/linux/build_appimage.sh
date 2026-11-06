#!/usr/bin/env bash
# Wraps the PyInstaller output in an AppImage: dist/FileConverter-<version>-x86_64.AppImage
# Run in CI after `pyinstaller packaging/file_converter.spec`.
set -euo pipefail
VERSION="$1"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APPDIR="$ROOT/build/AppDir"
rm -rf "$APPDIR" && mkdir -p "$APPDIR/usr/bin"
cp -r "$ROOT/dist/File Converter/." "$APPDIR/usr/bin/"
cp "$ROOT/packaging/linux/file-converter.desktop" "$APPDIR/"
cp "$ROOT/packaging/icon.png" "$APPDIR/file-converter.png"
cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/File Converter" "$@"
RUN
chmod +x "$APPDIR/AppRun"
TOOL="$ROOT/build/appimagetool"
if [ ! -x "$TOOL" ]; then
  curl -fsSL -o "$TOOL" https://github.com/AppImage/appimagetool/releases/download/1.9.0/appimagetool-x86_64.AppImage
  chmod +x "$TOOL"
fi
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" "$APPDIR" "$ROOT/dist/FileConverter-$VERSION-x86_64.AppImage"
