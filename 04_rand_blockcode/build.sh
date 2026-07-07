#!/usr/bin/env bash
# RAND_NLS_BlockCode — compile and run
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$ROOT/out"
CLASSES="$OUT/classes"
SRC="$ROOT/src"

mkdir -p "$CLASSES"

echo "== RAND BlockCode Java v1.0.1 =="
echo "ROOT: $ROOT"

mapfile -t SOURCES < <(find "$SRC" -name '*.java' | sort)
echo "Sources: ${#SOURCES[@]}"

javac -encoding UTF-8 -d "$CLASSES" -sourcepath "$SRC" "${SOURCES[@]}"
echo "Compile: OK"

java -cp "$CLASSES" com.nls.rand.RANDNLSLauncher "$ROOT/blocks/pipeline.json"