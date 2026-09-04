#!/bin/sh
set -eu

base_url=${1:?usage: verify-stack.sh BASE_URL}
allow_degraded=${2:-false}
attempt=0
while [ "$attempt" -lt 30 ]; do
  if readiness=$(curl -sS "$base_url/api/health/readiness" 2>/dev/null); then
    if printf '%s' "$readiness" | python3 -c 'import json,sys; raise SystemExit(0 if json.load(sys.stdin).get("ready") is True else 1)'; then
      echo "stack readiness: database and base analysis strategy ready"
      exit 0
    fi
    if [ "$allow_degraded" = "true" ] && printf '%s' "$readiness" | python3 -c 'import json,sys; data=json.load(sys.stdin); raise SystemExit(0 if data.get("status") == "degraded" and data.get("ready") is False else 1)'; then
      echo "stack reachable: shared base is intentionally missing an analysis strategy"
      exit 0
    fi
  fi
  attempt=$((attempt + 1))
  sleep 2
done
echo "stack health verification failed" >&2
exit 1
