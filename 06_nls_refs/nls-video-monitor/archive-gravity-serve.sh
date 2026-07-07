#!/usr/bin/env bash
# Archive gravity-serve snapshot — does NOT stop the live server.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
export NLS_VIDEO_HOME="${DIR}"
exec python3 "${DIR}/archive_gravity_serve.py" "$@"