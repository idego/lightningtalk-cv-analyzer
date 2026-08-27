# Operations

## Runtime

- Keep `CV_VALIDATOR_AI_ENABLED=false` unless AI analysis is intended.
- `OPENAI_API_KEY` is required when AI is enabled.
- Mount a validated GeoNames index and manifest; analysis never downloads them.
- Keep only the web service public. Persist and back up the SQLite volumes.
- Configure retention with `CV_VALIDATOR_RETENTION_DAYS`.

The current retry, batch, research-cache, and output limits are exposed by
`GET /operations/status`. Request totals, durations, research failures, and
cache metrics are exposed by `GET /operations/metrics`.

Logs contain identifiers, status, duration, and safe error codes. They must not
contain CV text, evidence, model output, secrets, or local paths. Upload bytes
are parsed in memory and are not stored.

## Failure and rollback

An AI failure leaves the deterministic report available. Manual retry reuses
only the redacted in-memory context and becomes unavailable after restart or
cleanup.

To return to deterministic-only operation, set
`CV_VALIDATOR_AI_ENABLED=false` and restart the API. Do not change weights or
thresholds as a rollback. Before rolling back a schema migration, stop writes
and back up SQLite.
