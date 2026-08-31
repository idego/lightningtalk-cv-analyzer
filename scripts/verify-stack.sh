#!/bin/sh
set -eu

base_url=${1:?usage: verify-stack.sh BASE_URL}
attempt=0
while [ "$attempt" -lt 30 ]; do
  if readiness=$(curl -fsS "$base_url/api/health/readiness" 2>/dev/null); then
    if printf '%s' "$readiness" | python3 -c 'import json,sys; raise SystemExit(0 if json.load(sys.stdin).get("ready") is True else 1)'; then
      echo "stack readiness: database, GeoNames, Document AI and research ready"
      exit 0
    fi
  fi
  attempt=$((attempt + 1))
  sleep 2
done
echo "stack health verification failed" >&2
exit 1
