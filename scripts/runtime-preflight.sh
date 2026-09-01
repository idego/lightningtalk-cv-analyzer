#!/bin/sh
set -eu

mode=${1:?usage: runtime-preflight.sh dev|production ENV_FILE}
env_file=${2:?usage: runtime-preflight.sh dev|production ENV_FILE}

fail() { echo "preflight: $*" >&2; exit 1; }
has_key() { grep -Eq "^[[:space:]]*$1=.+" "$env_file"; }
is_true() { grep -Eq "^[[:space:]]*$1=true[[:space:]]*$" "$env_file"; }
value_of() { sed -n "s/^[[:space:]]*$1=//p" "$env_file" | tail -n 1; }

[ -f "$env_file" ] || fail "missing $env_file"
if has_key CV_VALIDATOR_REFERENCE_DATA_DIR; then
  reference_dir=$(value_of CV_VALIDATOR_REFERENCE_DATA_DIR)
elif [ "$mode" = dev ]; then
  reference_dir=./data/geonames-build/2026-08-21
else
  fail "CV_VALIDATOR_REFERENCE_DATA_DIR is required"
fi
[ -n "$reference_dir" ] || fail "CV_VALIDATOR_REFERENCE_DATA_DIR is empty"
[ -f "$reference_dir/locations.sqlite3" ] || fail "missing pinned GeoNames index"
[ -f "$reference_dir/locations.manifest.json" ] || fail "missing pinned GeoNames manifest"

lock_file=config/geonames.lock
[ -f "$lock_file" ] || fail "missing $lock_file"
expected_index=$(sed -n 's/^index_sha256=//p' "$lock_file")
expected_manifest=$(sed -n 's/^manifest_sha256=//p' "$lock_file")
actual_index=$(sha256sum "$reference_dir/locations.sqlite3" | awk '{print $1}')
actual_manifest=$(sha256sum "$reference_dir/locations.manifest.json" | awk '{print $1}')
[ "$actual_index" = "$expected_index" ] || fail "GeoNames index checksum mismatch"
[ "$actual_manifest" = "$expected_manifest" ] || fail "GeoNames manifest checksum mismatch"

if [ "$mode" = dev ]; then
  if is_true CV_VALIDATOR_AI_ENABLED; then has_key OPENAI_API_KEY || fail "OPENAI_API_KEY is required when AI is enabled"; fi
elif [ "$mode" = production ]; then
  [ -z "$(git status --porcelain)" ] || fail "production deploy requires a clean worktree"
  grep -Eq '^[[:space:]]*LOCAL_DEV_AUTH_BYPASS=false[[:space:]]*$' "$env_file" || fail "LOCAL_DEV_AUTH_BYPASS must be false"
  grep -Eq '^[[:space:]]*WEB_HOST=127\.0\.0\.1[[:space:]]*$' "$env_file" || fail "WEB_HOST must be 127.0.0.1 behind the TLS reverse proxy"
  [ "${WEB_HOST:-127.0.0.1}" = "127.0.0.1" ] || fail "exported WEB_HOST must not override the production loopback binding"
  has_key BASE_URL || fail "BASE_URL is required"
  has_key BETTER_AUTH_URL || fail "BETTER_AUTH_URL is required"
  has_key BETTER_AUTH_SECRET || fail "BETTER_AUTH_SECRET is required"
  has_key GOOGLE_OAUTH_CLIENT_ID || fail "GOOGLE_OAUTH_CLIENT_ID is required"
  has_key GOOGLE_OAUTH_CLIENT_SECRET || fail "GOOGLE_OAUTH_CLIENT_SECRET is required"
  has_key ALLOWED_EMAIL_DOMAINS || fail "ALLOWED_EMAIL_DOMAINS is required"
  secret=$(value_of BETTER_AUTH_SECRET)
  [ ${#secret} -ge 32 ] || fail "BETTER_AUTH_SECRET must contain at least 32 characters"
  case "$secret" in *replace*|*change-me*|*dev-only*) fail "BETTER_AUTH_SECRET still uses a placeholder";; esac
  case "$(value_of BASE_URL)" in https://*) :;; *) fail "BASE_URL must use HTTPS";; esac
  if is_true CV_VALIDATOR_AI_ENABLED; then has_key OPENAI_API_KEY || fail "OPENAI_API_KEY is required when AI is enabled"; fi
  docker --context "${DOCKER_CONTEXT:-default}" compose --env-file "$env_file" config --quiet
  available_kb=$(df -Pk "$reference_dir" | awk 'NR==2 {print $4}')
  [ "$available_kb" -ge 1048576 ] || fail "less than 1 GiB free near GeoNames data"
else
  fail "unknown mode: $mode"
fi

echo "preflight: $mode configuration is valid"
