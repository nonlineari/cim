#!/usr/bin/env bash
# CIM Serve Hub — PHP built-in server with router (shared nav + CIM archive files).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-8765}"
HOST="${2:-127.0.0.1}"

PHP=""
if command -v php >/dev/null 2>&1; then
  PHP="$(command -v php)"
elif [[ -x "$DIR/.php-bin/php" ]]; then
  PHP="$DIR/.php-bin/php"
fi

if [[ -z "${PHP:-}" ]]; then
  echo "PHP not found. Install php-cli or run: curl -fsSL -o $DIR/.php-bin/php.tar.gz \\"
  echo "  https://dl.static-php.dev/static-php-cli/bulk/php-8.3.32-cli-linux-x86_64.tar.gz"
  echo "  && tar -xzf $DIR/.php-bin/php.tar.gz -C $DIR/.php-bin"
  exit 1
fi

cd "$DIR"
echo "CIM Serve Hub → http://${HOST}:${PORT}/index.php"
echo "PHP: $($PHP -v | head -1)"
exec "$PHP" -S "${HOST}:${PORT}" router.php