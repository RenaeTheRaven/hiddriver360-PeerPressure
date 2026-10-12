#!/bin/bash
# Builds Team-Resurgent XexTool (pinned commit) into build/xextool/XexTool.
# Needs git and clang/clang++ (or cmake + a C++17 compiler).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMMIT=ed52481   # "ElfPacker: accept ELFCLASS64 input"; the loaders were built with this version
SRC="$ROOT/build/xextool-src"
OUT="$ROOT/build/xextool"

if [ ! -d "$SRC/.git" ]; then
  git clone --quiet https://github.com/Team-Resurgent/XexTool.git "$SRC"
fi
git -C "$SRC" fetch --quiet origin
git -C "$SRC" checkout --quiet "$COMMIT"
git -C "$SRC" submodule --quiet update --init --recursive   # XeCrypt, libLZX, tinyxml2
mkdir -p "$OUT"

if command -v cmake >/dev/null; then
  cmake -S "$SRC" -B "$OUT/cmake" -DCMAKE_BUILD_TYPE=Release >/dev/null
  cmake --build "$OUT/cmake" -j >/dev/null
  cp "$(find "$OUT/cmake" -type f -name XexTool -perm -u+x | head -1)" "$OUT/XexTool"
else
  # Plain clang build (no cmake).
  cd "$SRC"
  X=third_party/XeCrypt
  INC="-I$X -I$X/aes -I$X/md5 -I$X/rc4 -I$X/sha -I$X/bign -I$X/des -Ithird_party/libLZX -Isrc -Isrc/lzx -Ithird_party/tinyxml2"
  OBJ="$OUT/obj"; mkdir -p "$OBJ"
  for f in $X/xecrypt.c $X/xecryptBn.c $X/xecryptHmacSha.c $X/aes/*.c $X/md5/*.c $X/rc4/*.c \
           $X/sha/*.c $X/bign/*.c $X/des/*.c third_party/libLZX/lzx/lzx_encoder.c \
           third_party/libLZX/lzx/lzx_decoder.c src/*.c; do
    clang -w -O2 -std=gnu11 $INC -c "$f" -o "$OBJ/$(echo "$f" | tr / _).o"
  done
  for f in src/*.cpp src/lzx/*.cpp third_party/tinyxml2/tinyxml2.cpp; do
    clang++ -w -O2 -std=c++17 $INC -c "$f" -o "$OBJ/$(echo "$f" | tr / _).o"
  done
  clang++ "$OBJ"/*.o -o "$OUT/XexTool"
fi
echo "built $OUT/XexTool"
