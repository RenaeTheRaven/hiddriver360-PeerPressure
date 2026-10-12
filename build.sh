#!/bin/bash
# Builds the loaders and assembles the PeerPressure Softmod Extra.
#   ./build.sh --peerpressure <SoftmodInstaller.zip | BadUpdatePayload folder | SoftmodData.zip>
#              [--install-into <BadUpdatePayload folder on your USB stick>]
# XexTool: $XEXTOOL, else build/xextool/XexTool (tools/build-xextool.sh), else XexTool on PATH.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [ -z "${XEXTOOL:-}" ]; then
  if [ -x "$ROOT/build/xextool/XexTool" ]; then XEXTOOL="$ROOT/build/xextool/XexTool"
  elif command -v XexTool >/dev/null; then XEXTOOL="$(command -v XexTool)"
  else echo "XexTool not found: run tools/build-xextool.sh or set XEXTOOL" >&2; exit 1; fi
fi
export XEXTOOL

"$ROOT/loader/build.sh"
(cd "$ROOT/loader" && sha256sum -c SHA256SUMS) || {
  echo "warning: loader build differs from loader/SHA256SUMS (different clang/XexTool?)" >&2; }
(cd "$ROOT/hiddriver/prebuilt" && sha256sum -c SHA256SUMS)

if [ $# -gt 0 ]; then
  python3 "$ROOT/tools/make-extra.py" "$@"
else
  echo "loaders built; pass --peerpressure <PeerPressure download> to assemble the Extra"
fi
