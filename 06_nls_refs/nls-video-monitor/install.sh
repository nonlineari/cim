#!/usr/bin/env bash
set -euo pipefail

echo "Installing nls-video (NLS Video Pipeline + Monitor) ..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$HOME/.local/bin/nls-video"

mkdir -p "$(dirname "$TARGET")"
# Remove symlink first — old installs linked nls-video → nls_video_pipe.py (writing would corrupt source).
rm -f "$TARGET"
cat > "$TARGET" <<EOF
#!/usr/bin/env bash
# Wrapper — gravity-serve must not resolve assets from ~/.local/bin (root/user path issues).
export NLS_VIDEO_HOME="${SCRIPT_DIR}"
exec python3 "\${NLS_VIDEO_HOME}/nls_video_pipe.py" "\$@"
EOF
chmod +x "$TARGET"

echo "Installed → $TARGET"
echo "  NLS_VIDEO_HOME=${SCRIPT_DIR}"
echo
echo "Make sure ~/.local/bin is in your PATH (usually is on Ubuntu)."
echo "Try: nls-video --help"
echo
echo "Recommended:"
echo "  1. nls-video add 'https://youtube.com/...' --preset balanced-4k"
echo "  2. Run the worker in tmux:  nls-video worker"
echo "  3. Live TUI:               nls-video monitor"
echo "  4. Browser dashboard:      ./run-gravity-serve.sh  (not from bin — uses project root)"
echo
echo "Finished videos + .nlsvis.json metadata will land in ~/Videos/NLS-Visualist/"
echo "Central catalog for your Visualist tools: ~/.local/share/nls-video/visualist_catalog.json"