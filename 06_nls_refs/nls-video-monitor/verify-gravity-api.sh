#!/usr/bin/env bash
# Verify gravity-serve locally: /api/gravity, /api/downloads, /api/logs
# Usage: ./verify-gravity-api.sh [base_url]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8766}"
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${HOME}/.local/share/gravity-desktop/runtime-logs"
STAMP="$(date -u +%Y-%m-%dT%H%M%SZ)"
REPORT="${LOG_DIR}/verify-${STAMP}.json"
mkdir -p "$LOG_DIR"
EXPECTED_VERSION="$(python3 -c "import json; print(json.load(open('${DIR}/version.json')).get('version',''))" 2>/dev/null || echo "")"

pass=0
fail=0

check() {
  local name="$1" code="$2" expected="$3"
  if [[ "$code" == "$expected" ]]; then
    echo "  ✓ $name (HTTP $code)"
    pass=$((pass + 1))
  else
    echo "  ✗ $name (HTTP $code, expected $expected)"
    fail=$((fail + 1))
  fi
}

echo "Gravity API verification → $BASE"
[[ -n "$EXPECTED_VERSION" ]] && echo "Expected version: v${EXPECTED_VERSION}"
echo ""

code=$(curl -s -o /tmp/gravity-version.json -w "%{http_code}" "${BASE}/api/version" || echo "000")
if [[ "$code" == "200" ]]; then
  echo "  ✓ /api/version (HTTP 200)"
  pass=$((pass + 1))
  python3 -c "
import json
d=json.load(open('/tmp/gravity-version.json'))
exp='${EXPECTED_VERSION}'
ver=d.get('version','')
print(f'    version={ver} tag={d.get(\"tag\",\"—\")}')
if exp and ver != exp:
    raise SystemExit(1)
"
  if [[ $? -eq 0 ]]; then
    pass=$((pass + 1))
    echo "  ✓ /api/version matches version.json"
  else
    fail=$((fail + 1))
    echo "  ✗ /api/version mismatch (restart gravity-serve?)"
  fi
else
  echo "  ✗ /api/version (HTTP $code — restart gravity-serve if 404)"
  fail=$((fail + 1))
fi
echo ""

code=$(curl -s -o /tmp/gravity-api.json -w "%{http_code}" "${BASE}/api/gravity" || echo "000")
check "/api/gravity" "$code" "200"
if [[ -f /tmp/gravity-api.json ]]; then
  python3 -c "
import json
d=json.load(open('/tmp/gravity-api.json'))
assert 'jobs' in d and isinstance(d['jobs'], list)
assert 'catalog' in d
print(f\"    jobs={len(d['jobs'])} catalog={len(d['catalog'])} connected={d.get('connected')}\")
"
  pass=$((pass + 1))
  echo "  ✓ /api/gravity JSON schema"
else
  fail=$((fail + 1))
  echo "  ✗ /api/gravity JSON missing"
fi
echo ""

code=$(curl -s -o /tmp/gravity-dl.json -w "%{http_code}" "${BASE}/api/downloads" || echo "000")
check "/api/downloads" "$code" "200"
if [[ -f /tmp/gravity-dl.json ]]; then
  python3 -c "
import json
d=json.load(open('/tmp/gravity-dl.json'))
items=d.get('items',[])
assert isinstance(items, list)
print(f'    items={len(items)}')
if items: print(f\"    sample={items[0].get('name')} pattern={items[0].get('pattern_code','—')}\")
"
  pass=$((pass + 1))
  echo "  ✓ /api/downloads JSON schema"
else
  fail=$((fail + 1))
  echo "  ✗ /api/downloads JSON missing"
fi
echo ""

code=$(curl -s -o /tmp/gravity-cancel.json -w "%{http_code}" -X POST "${BASE}/api/cancel" \
  -H "Content-Type: application/json" -d '{"id":0}' || echo "000")
if [[ "$code" == "200" || "$code" == "400" ]]; then
  echo "  ✓ /api/cancel (HTTP $code, JSON API reachable)"
  pass=$((pass + 1))
  python3 -c "
import json
d=json.load(open('/tmp/gravity-cancel.json'))
assert 'ok' in d
print(f\"    ok={d.get('ok')} error={d.get('error','—')}\")
"
  pass=$((pass + 1))
  echo "  ✓ /api/cancel JSON schema"
else
  echo "  ✗ /api/cancel (HTTP $code — restart gravity-serve if 404 HTML)"
  fail=$((fail + 1))
fi
echo ""

code=$(curl -s -o /tmp/gravity-logs.json -w "%{http_code}" "${BASE}/api/logs" || echo "000")
if [[ "$code" == "200" ]]; then
  echo "  ✓ /api/logs (HTTP 200)"
  pass=$((pass + 1))
  python3 -c "
import json
d=json.load(open('/tmp/gravity-logs.json'))
print(f\"    runtime_ms={d.get('runtime_ms')} tail_lines={len(d.get('tail') or [])}\")
print(f\"    live_log={d.get('live_log')}\")
"
else
  echo "  ○ /api/logs not available (HTTP $code)"
fi
echo ""

python3 -c "
import json, os
from datetime import datetime, timezone
report = {
    'verified_at': datetime.now(timezone.utc).isoformat(),
    'base_url': '${BASE}',
    'expected_version': '${EXPECTED_VERSION}' or None,
    'passed': ${pass},
    'failed': ${fail},
}
if os.path.isfile('${DIR}/version.json'):
    report['manifest'] = json.load(open('${DIR}/version.json'))
if os.path.isfile('/tmp/gravity-version.json'):
    report['version_api'] = json.load(open('/tmp/gravity-version.json'))
if os.path.isfile('/tmp/gravity-api.json'):
    report['gravity'] = json.load(open('/tmp/gravity-api.json'))
if os.path.isfile('/tmp/gravity-dl.json'):
    report['downloads'] = json.load(open('/tmp/gravity-dl.json'))
if os.path.isfile('/tmp/gravity-logs.json') and os.path.getsize('/tmp/gravity-logs.json') > 2:
    try:
        report['logs'] = json.load(open('/tmp/gravity-logs.json'))
    except Exception:
        pass
with open('${REPORT}', 'w') as f:
    json.dump(report, f, indent=2, default=str)
print(f'Report saved: ${REPORT}')
"

echo ""
echo "Runtime logs (live JSONL):"
echo "  gravity-serve:   ${LOG_DIR}/gravity-serve-live.jsonl"
echo "  gravity-desktop: ${LOG_DIR}/gravity-desktop-live.jsonl"
echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "RESULT: PASS (${pass} checks)"
  exit 0
else
  echo "RESULT: FAIL (${fail} failed, ${pass} passed)"
  echo "Start: ~/Downloads/GravityDesktop/run-gravity-serve.sh"
  exit 1
fi