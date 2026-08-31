# Operations

## Runtime

- Keep `CV_VALIDATOR_AI_ENABLED=false` unless AI analysis is intended.
- `OPENAI_API_KEY` is required when AI is enabled.
- Mount a validated GeoNames index and manifest; analysis never downloads them.
- Keep only the web service public. Persist and back up the SQLite volumes.
- Configure retention with `CV_VALIDATOR_RETENTION_DAYS`.
- Link inspection is enabled by default but can be placed in neutral degraded
  mode with `CV_VALIDATOR_LINK_CHECK_ENABLED=false`.
- Keep link checks on the bounded defaults unless a measured deployment needs a
  change. `CV_VALIDATOR_LINK_CHECK_TIMEOUT_SECONDS`,
  `CV_VALIDATOR_LINK_CHECK_MAX_RESPONSE_BYTES`,
  `CV_VALIDATOR_LINK_CHECK_MAX_REDIRECTS`,
  `CV_VALIDATOR_LINK_CHECK_MAX_CONCURRENCY`,
  `CV_VALIDATOR_LINK_CHECK_MAX_RETRIES`, and
  `CV_VALIDATOR_LINK_CHECK_TOTAL_BUDGET_SECONDS` are exposed through
  `GET /operations/status`.
- Link checks are public HTTP(S) document-declaration checks only. They reject
  credentials, non-allowlisted ports, private/link-local/reserved/multicast/
  metadata destinations, and unsafe redirect hops. Requests use no cookies or
  candidate credentials, do not execute JavaScript or download linked files,
  and discard response bodies after bounded classification.

The user-facing Settings switch is a per-browser opt-out covering Document AI,
company research, education research, and LinkedIn discovery. Turning it off
blocks both automatic and manual execution; it does not change deterministic
analysis or the deployment environment.

## Canonical commands

Local development uses an ignored `.env.local` and the approved GeoNames pair:

```bash
cp .env.example .env.local
# set CV_VALIDATOR_AI_ENABLED=true, OPENAI_API_KEY, and the reference-data path
make dev
```

Production uses an ignored `.env`. On the VPS, check out an exact reviewed SHA,
place the pinned GeoNames pair at the configured path, then run:

```bash
make deploy-check
make deploy
```

The host reverse proxy terminates TLS and forwards only to the web port bound
on `127.0.0.1`. The API remains private to Compose. Both commands verify the
non-sensitive `/api/health/readiness` endpoint and fail without healthy
database, GeoNames, Document AI, and research capabilities.

## Backups and restore

Back up both named volumes before deployment or rollback. Do not copy a live
SQLite file directly; stop the stack or use SQLite's online backup command from
a temporary container. Store encrypted backups outside the VPS and record the
deployed Git SHA and GeoNames snapshot with each backup.

A restore rehearsal must use a separate temporary Compose project: create new
volumes, restore both databases, start the same reviewed SHA, and verify login,
history, `/api/health`, and one synthetic analysis. Never rehearse against the
production volumes. Keep at least the previous reviewed image/commit and
GeoNames snapshot. Container logs are rotated by Compose at 10 MiB with three
files; monitor host disk and the public health URL separately.

The current retry, batch, research-cache, and output limits are exposed by
`GET /operations/status`. Request totals, durations, research failures, and
cache metrics are exposed by `GET /operations/metrics`.

Logs contain identifiers, status, duration, and safe error codes. They must not
contain CV text, evidence, model output, secrets, or local paths. Upload bytes
are parsed in memory and are not stored. Link metrics contain only status and
stable reason codes; they must not contain URLs, CV text, query strings,
credentials, cookies, response bodies, or headers.

`SUSPICIOUS` means that a concrete document declaration needs human review. It
does not mean that a candidate lied or that fraud was proven. `UNAVAILABLE`
means that a network, access-control, anti-bot, or request-budget limit made
the check inconclusive. These outcomes never change the deterministic score,
band, AI output, or hiring action.

## Failure and rollback

An AI failure leaves the deterministic report available. Manual retry reuses
only the redacted in-memory context and becomes unavailable after restart or
cleanup.

To return to deterministic-only operation, set
`CV_VALIDATOR_AI_ENABLED=false` and restart the API. Do not change weights or
thresholds as a rollback. Before rolling back a schema migration, stop writes
and back up SQLite. To disable only external link requests while retaining
document link inventory, set `CV_VALIDATOR_LINK_CHECK_ENABLED=false`; this
produces neutral `UNAVAILABLE`/inspection-disabled results and leaves the base
report and scoring path unchanged.

For an application rollback, check out the previously recorded reviewed SHA
and run `make deploy`; named volumes are preserved. Restore databases only when
the application rollback is insufficient or a schema rollback explicitly
requires it.
