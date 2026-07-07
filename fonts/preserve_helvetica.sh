#!/usr/bin/env bash
# Archive URW NimbusSans (Helvetica PDF substitute) into CIM before host removal.
set -euo pipefail
DEST="$(cd "$(dirname "$0")" && pwd)/CIM-Visualist/Helvetica/NimbusSans"
SRC="${URW_FONTS:-/usr/share/fonts/type1/urw-base35}"
mkdir -p "$DEST"
for f in NimbusSans-Regular NimbusSans-Bold NimbusSans-Italic NimbusSans-BoldItalic NimbusMonoPS-Regular; do
  for ext in afm t1; do
    [ -e "$SRC/${f}.${ext}" ] && cp -L "$SRC/${f}.${ext}" "$DEST/"
  done
done
echo "Preserved $(ls "$DEST" | wc -l) files → $DEST"
python3 "$(dirname "$0")/cim_visualist_typography.py" 2>/dev/null || true