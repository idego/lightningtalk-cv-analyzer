#!/bin/sh
set -eu

base_url=${1:?usage: verify-stack.sh BASE_URL}
attempt=0
while [ "$attempt" -lt 30 ]; do
  if health=$(curl -fsS "$base_url/api/health" 2>/dev/null); then
    if printf '%s' "$health" | python3 -c 'import json,sys; h=json.load(sys.stdin); required=("database","geonames","document_ai","company_research","education_research","linkedin_research"); raise SystemExit(0 if all(h.get("capabilities",{}).get(k,{}).get("ready") is True for k in required) else 1)'; then
      echo "stack health: database, GeoNames, Document AI and research ready"
      exit 0
    fi
  fi
  attempt=$((attempt + 1))
  sleep 2
done
echo "stack health verification failed" >&2
exit 1
