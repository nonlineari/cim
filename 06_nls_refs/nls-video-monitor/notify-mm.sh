#!/usr/bin/env bash
# Tell mm what's running — prints gravity-serve running version + mm-notify.json path.
set -euo pipefail
export NLS_VIDEO_HOME="$(cd "$(dirname "$0")" && pwd)"
nls-video running-status "$@"