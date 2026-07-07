#!/usr/bin/env bash
# Safe restart — avoids pkill -f matching the wrapper shell (SIGTERM to self).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${GRAVITY_SERVE_PORT:-8766}"

stop_gravity_serve() {
  local pids
  pids=$(pgrep -f '[n]ls_video_pipe.py gravity-serve' 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    echo "Stopping gravity-serve: $pids"
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

stop_gravity_serve
exec "${DIR}/run-gravity-serve.sh" "$@"