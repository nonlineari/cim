#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
export PATH="${HOME}/.deno/bin:/usr/bin:/usr/local/bin:${HOME}/.local/bin:${PATH}"
# Optional: source ~/.config/gravity-desktop/env (from setup-cookies.sh --use-browser)
[[ -f "${HOME}/.config/gravity-desktop/env" ]] && source "${HOME}/.config/gravity-desktop/env"
PORT="${GRAVITY_SERVE_PORT:-8766}"
GRAVITY_PORT="${GRAVITY_SERVER_PORT:-4242}"
echo "Gravity Serve → http://127.0.0.1:${PORT}/"
echo "Ensure gravity-server is running: nls-video gravity-server --port ${GRAVITY_PORT}"
exec python3 "${DIR}/nls_video_pipe.py" gravity-serve --port "${PORT}" --gravity-port "${GRAVITY_PORT}" "$@"