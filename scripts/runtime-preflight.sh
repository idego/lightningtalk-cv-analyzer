#!/bin/sh
set -eu

mode=${1:?usage: runtime-preflight.sh dev|production ENV_FILE automatic|operator}
env_file=${2:?usage: runtime-preflight.sh dev|production ENV_FILE automatic|operator}
reference_mode=${3:-automatic}

fail() { echo "preflight: $*" >&2; exit 1; }
has_key() { grep -Eq "^[[:space:]]*$1=.+" "$env_file"; }
value_of() { sed -n "s/^[[:space:]]*$1=//p" "$env_file" | tail -n 1; }
validate_ai_configuration() {
  ai_enabled=$(value_of CV_VALIDATOR_AI_ENABLED)
  case "${ai_enabled:-true}" in
    true) has_key OPENAI_API_KEY || fail "OPENAI_API_KEY is required when AI is enabled";;
    false) :;;
    *) fail "CV_VALIDATOR_AI_ENABLED must be true or false";;
  esac
}

[ -f "$env_file" ] || fail "missing $env_file"
case "$reference_mode" in
  automatic)
    snapshot_version=$(value_of GEONAMES_SNAPSHOT_VERSION)
    if [ -z "$snapshot_version" ] && [ "$mode" = dev ]; then snapshot_version=2026-09-02; fi
    [ -n "$snapshot_version" ] || fail "GEONAMES_SNAPSHOT_VERSION is required"
    echo "$snapshot_version" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' || fail "GEONAMES_SNAPSHOT_VERSION must use YYYY-MM-DD"
    for key in GEONAMES_CITIES500_URL GEONAMES_COUNTRY_INFO_URL GEONAMES_ALTERNATE_NAMES_URL GEONAMES_POSTAL_CODES_URL; do
      if has_key "$key"; then
        case "$(value_of "$key")" in https://*) :;; *) fail "$key must use HTTPS";; esac
      fi
    done
    compose_files="-f docker-compose.yml"
    ;;
  operator)
    has_key CV_VALIDATOR_REFERENCE_DATA_DIR || fail "CV_VALIDATOR_REFERENCE_DATA_DIR is required in operator mode"
    reference_dir=$(value_of CV_VALIDATOR_REFERENCE_DATA_DIR)
    [ -d "$reference_dir" ] || fail "reference-data directory does not exist"
    for file in locations.sqlite3 locations.manifest.json postal-codes.sqlite3 postal-codes.manifest.json; do
      [ -f "$reference_dir/$file" ] || fail "missing operator GeoNames file: $file"
    done
    lock_file=config/geonames.lock
    [ -f "$lock_file" ] || fail "missing $lock_file"
    expected_index=$(sed -n 's/^index_sha256=//p' "$lock_file")
    expected_manifest=$(sed -n 's/^manifest_sha256=//p' "$lock_file")
    actual_index=$(sha256sum "$reference_dir/locations.sqlite3" | awk '{print $1}')
    actual_manifest=$(sha256sum "$reference_dir/locations.manifest.json" | awk '{print $1}')
    [ "$actual_index" = "$expected_index" ] || fail "GeoNames index checksum mismatch"
    [ "$actual_manifest" = "$expected_manifest" ] || fail "GeoNames manifest checksum mismatch"
    compose_files="-f docker-compose.yml -f docker-compose.reference-data.yml"
    space_path=$reference_dir
    ;;
  *) fail "reference-data mode must be automatic or operator";;
esac

if [ "$mode" = dev ]; then
  validate_ai_configuration
elif [ "$mode" = production ]; then
  [ -z "$(git status --porcelain)" ] || fail "production deploy requires a clean worktree"
  grep -Eq '^[[:space:]]*LOCAL_DEV_AUTH_BYPASS=false[[:space:]]*$' "$env_file" || fail "LOCAL_DEV_AUTH_BYPASS must be false"
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
  validate_ai_configuration
  # shellcheck disable=SC2086
  docker --context "${DOCKER_CONTEXT:-default}" compose $compose_files --env-file "$env_file" config --quiet
  if [ "$reference_mode" = automatic ]; then
    available_kb=$(
      docker --context "${DOCKER_CONTEXT:-default}" run --rm --pull=missing --network none python:3.12-slim \
        df -Pk / | awk 'NR==2 {print $4}'
    )
  else
    available_kb=$(df -Pk "$space_path" | awk 'NR==2 {print $4}')
  fi
  minimum_kb=${GEONAMES_MIN_FREE_KB:-3145728}
  [ "$available_kb" -ge "$minimum_kb" ] || fail "less than 3 GiB free for GeoNames initialization"
else
  fail "unknown mode: $mode"
fi

echo "preflight: $mode configuration is valid"
